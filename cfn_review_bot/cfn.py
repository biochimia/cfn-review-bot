import datetime
import hashlib
import json
import time

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Mapping, Optional

from . import error
from . import loader

from .merge import deep_merge


CFN_METADATA_PARAMETER = 'ReviewBotMetadata'


class ValidationError(error.Error):
  pass


class TimeoutError(error.Error):
  pass


def _cfn_fn_handler(data):
  if isinstance(data, loader.OpaqueTagValue):
    return {'Fn::{}'.format(data.tag[1:]): data.value}
  raise TypeError(
    'Object of type {} is not JSON serializable'.format(type(data)))


class Stack:
  def __init__(
    self,
    *,
    name,
    template,
    capabilities=None,
    parameters=None,
    tags=None,
    project=None):

    self.name = name
    self.template = template
    self.capabilities = capabilities or []
    self.parameters = parameters or {}
    self.tags = tags or {}
    self.project = project or None

  @property
  def canonical_content(self):
    content = {
      'template': self.template,
      'parameters': self.parameters,
      'tags': self.tags,
    }
    if self.project:
      content['project'] = self.project
    return json.dumps(
      content,
      allow_nan=False,
      check_circular=True,
      default=_cfn_fn_handler,
      ensure_ascii=True,
      separators=(',', ':'),
      sort_keys=True,
    ).encode('utf-8')

  @property
  def content_hash(self):
    h = hashlib.sha256(self.canonical_content)
    return 'sha256-{}'.format(h.hexdigest())


class DeployedStack(dict):
  def __init__(self, other, *, metadata_parameter, metadata_suffix):
    super().__init__(other)
    self.metadata_parameter = metadata_parameter
    self.metadata_suffix = metadata_suffix

  @property
  def status(self):
    return self['StackStatus']

  @property
  def exists(self):
    return self.status not in ('REVIEW_IN_PROGRESS', 'ROLLBACK_COMPLETE')

  @property
  def parameters(self):
    return {
      p['ParameterKey']: p['ParameterValue']
      for p in self.get('Parameters') or {}
    }

  @property
  def is_unmanaged(self):
    return not self.parameters.get(self.metadata_parameter)

  @property
  def content_hash(self):
    metadata = self.parameters.get(self.metadata_parameter)
    if (metadata is not None
        and metadata.endswith(self.metadata_suffix)):
      return metadata[:-len(self.metadata_suffix)]


class ChangeSetType(Enum):
  CREATE = 'CREATE'
  UPDATE = 'UPDATE'


@dataclass
class ChangeSet:
  type: ChangeSetType
  stack: str
  id: str
  detail: Optional[Mapping[str, Any]] = None


@dataclass
class StackStats:
  total: int = 0
  new: int = 0
  updated: int = 0
  adopted: int = 0
  orphaned: int = 0
  unmanaged: int = 0

  def __str__(self):
    parts = []

    if self.new:
      parts += [f'{self.new} new']
    if self.updated:
      parts += [f'{self.updated} updated']
      if self.adopted:
        parts[-1] += f' ({self.adopted} adopted)'
    if self.orphaned:
      parts += [f'{self.orphaned} orphaned']

    if not parts:
      parts = ['unchanged']

    return f'{" | ".join(parts)} (total: {self.total}, unmanaged: {self.unmanaged})'


@dataclass
class ProcessStacksResult:
  stack_summary: StackStats = field(default_factory=StackStats)
  change_sets: List[ChangeSet] = field(default_factory=list)
  orphaned_stacks: List[DeployedStack] = field(default_factory=list)


class Target:
  metadata_parameter = CFN_METADATA_PARAMETER

  def __init__(self, cfn, *, project):
    self.cfn = cfn
    self.project = project

  @property
  def metadata_suffix(self):
    return '@{}'.format(self.project) if self.project else ''

  @property
  def deployed_stacks(self):
    try:
      return self._stack
    except AttributeError:
      pass

    self._stack = {
      s['StackName']: DeployedStack(s,
        metadata_parameter=self.metadata_parameter,
        metadata_suffix=self.metadata_suffix)
      for s in self.cfn.describe_stacks()['Stacks'] }

    return self._stack

  def process_single_stack(self, s, *, dry_run=False):
    stack = Stack(**s, project=self.project)
    stack_id = stack.name
    content_hash = stack.content_hash

    deployed = self.deployed_stacks.get(stack.name)
    if (deployed
        and deployed.status != 'REVIEW_IN_PROGRESS'):

      if deployed.status == 'ROLLBACK_COMPLETE':
        raise ValidationError(
          'Stack {} with ROLLBACK_COMPLETE status needs to be deleted before '
          'it can be recreated.'
          .format(stack.name))

      deployed.is_outdated = (content_hash != deployed.content_hash)
      if not deployed.is_outdated:
        return None

      stack_id = deployed['StackId']
      change_set_type = ChangeSetType.UPDATE
    else:
      change_set_type = ChangeSetType.CREATE

    template = deep_merge(
      {
        'Parameters': {
          self.metadata_parameter: {'Type': 'String'}
        }
      },
      stack.template)

    template_body = loader.dump_yaml(template, stream=None)
    v = self.cfn.validate_template(TemplateBody=template_body)

    for cap in v.get('Capabilities', []):
      if cap not in stack.capabilities:
        reason = v.get('CapabilitiesReason', '(no reason provided)')
        raise ValidationError(
          'Required capability, {}, is missing in stack {}: {}'
          .format(cap, stack.name, reason))

    parameters = [
      {
        'ParameterKey': self.metadata_parameter,
        'ParameterValue': content_hash + self.metadata_suffix,
      },
    ]
    parameters.extend(
      {'ParameterKey': k, 'ParameterValue': v}
      for k, v in stack.parameters.items())

    tags = [{'Key': k, 'Value': v} for k, v in stack.tags.items()]

    change_set_id = None
    if not dry_run:
      change_set = self.cfn.create_change_set(
        StackName=stack.name,
        TemplateBody=template_body,
        Capabilities=stack.capabilities,
        ChangeSetType=change_set_type.value,
        ChangeSetName=content_hash,
        Parameters=parameters,
        Tags=tags,
      )

      change_set_id = change_set['Id']
      stack_id = change_set['StackId']

    return ChangeSet(change_set_type, stack_id, change_set_id)

  def process_stacks(self, managed_stacks, *, dry_run=False):
    result = ProcessStacksResult()

    for s in managed_stacks:
      change_set = self.process_single_stack(s, dry_run=dry_run)
      if change_set is None:
        continue

      if change_set.type == ChangeSetType.CREATE:
        result.stack_summary.total += 1
        result.stack_summary.new += 1
      elif change_set.type == ChangeSetType.UPDATE:
        result.stack_summary.updated += 1

      result.change_sets.append(change_set)

    for n, s in self.deployed_stacks.items():
      result.stack_summary.total += 1

      if hasattr(s, 'is_outdated'):
        # Managed (or now adopted) stack
        if not s.content_hash:
          result.stack_summary.adopted += 1
        continue

      if s.content_hash:
        result.stack_summary.orphaned += 1
        result.orphaned_stacks.append(n)
      elif s.is_unmanaged:
        result.stack_summary.unmanaged += 1

    return result

  def wait_for_ready(self, change_set: ChangeSet):
    if change_set.id is None:
      return

    start = datetime.datetime.now()
    while True:
      detail = self.cfn.describe_change_set(ChangeSetName=change_set.id)

      if detail['Status'] not in ['CREATE_PENDING', 'CREATE_IN_PROGRESS']:
        change_set.detail = detail
        return

      if (datetime.datetime.now() - start).total_seconds() > 60:
        raise TimeoutError(
          f'Timeout waiting for change set {change_set.id} to become ready')

      time.sleep(5)
