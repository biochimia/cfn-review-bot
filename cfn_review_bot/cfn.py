import hashlib
import json

from . import error
from . import loader

from .merge import deep_merge


CFN_METADATA_PARAMETER = 'ReviewBotMetadata'


class ValidationError(error.Error):
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
  def content_hash(self):
    metadata = self.parameters.get(self.metadata_parameter)
    if (metadata is not None
        and metadata.endswith(self.metadata_suffix)):
      return metadata[:-len(self.metadata_suffix)]


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
    content_hash = stack.content_hash

    deployed = self.deployed_stacks.get(stack.name)
    if deployed:
      if deployed.status == 'ROLLBACK_COMPLETE':
        raise ValidationError(
          'Stack {} with ROLLBACK_COMPLETE status needs to be deleted before '
          'it can be recreated.'
          .format(stack.name))

      deployed.is_outdated = (content_hash != deployed.content_hash)
      if not deployed.is_outdated:
        return None, None

      change_set_type = 'UPDATE'
    else:
      change_set_type = 'CREATE'

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
      change_set_id = self.cfn.create_change_set(
        StackName=stack.name,
        TemplateBody=template_body,
        Capabilities=stack.capabilities,
        ChangeSetType=change_set_type,
        ChangeSetName=content_hash,
        Parameters=parameters,
        Tags=tags,
      )['Id']

    return change_set_type, change_set_id

  def process_stacks(self, managed_stacks, *, dry_run=False):
    new_stack_count = 0
    updated_stack_count = 0
    adopted_stack_count = 0
    unmanaged_stack_count = 0

    change_set_ids = []
    orphaned_stacks = []

    for s in managed_stacks:
      change_set_type, change_set_id = self.process_single_stack(s, dry_run=dry_run)

      if change_set_type is None:
        continue

      if change_set_type == 'CREATE':
        new_stack_count += 1
      elif change_set_type == 'UPDATE':
        updated_stack_count += 1

      if change_set_id is not None:
        change_set_ids.append(change_set_id)

    for n, s in self.deployed_stacks.items():
      if hasattr(s, 'is_outdated'):
        # Managed (or now adopted) stack
        if not s.content_hash:
          adopted_stack_count += 1
        continue

      if s.content_hash:
        orphaned_stacks.append(n)
      else:
        unmanaged_stack_count += 1

    return {
      'change-set-id': change_set_ids,
      'orphaned-stack': orphaned_stacks,
      'stack-count': {
        'total': len(self.deployed_stacks) + new_stack_count,
        'new': new_stack_count,
        'updated': updated_stack_count,
        'adopted': adopted_stack_count,
        'orphaned': len(orphaned_stacks),
        'unmanaged': unmanaged_stack_count,
      },
    }
