import hashlib
import json

from . import aws
from . import error
from . import loader


CONTENT_HASH_TAG = 'cfn-review-bot-hash'


class ValidationError(error.Error):
  pass


def _cfn_fn_handler(data):
  if isinstance(data, loader.OpaqueTagValue):
    return {'Fn::{}'.format(data.tag[1:]): data.value}
  raise TypeError(
    'Object of type {} is not JSON serializable'.format(type(data)))


class Stack:
  def __init__(
    self, name, template, capabilities=None, parameters=None, tags=None):

    self.name = name
    self.template = template
    self.capabilities = capabilities or []
    self.parameters = parameters or {}
    self.tags = tags or {}

  @property
  def template_body(self):
    return self.template.__raw__

  @property
  def canonical_content(self):
    return json.dumps(
      {
        'name': self.name,
        'template': self.template,
        'parameters': self.parameters,
        'tags': self.tags,
      },
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
  @property
  def status(self):
    return self['StackStatus']

  @property
  def exists(self):
    return self.status not in ('REVIEW_IN_PROGRESS', 'ROLLBACK_COMPLETE')

  @property
  def tags(self):
    return { t['Key']: t['Value'] for t in self['Tags'] }

  @property
  def content_hash(self):
    return self.tags.get(CONTENT_HASH_TAG)


class Target:
  def __init__(self, cfn):
    self.cfn = cfn

  @property
  def deployed_stacks(self):
    try:
      return self._stack
    except AttributeError:
      pass

    self._stack = {
      s['StackName']: DeployedStack(s)
      for s in self.cfn.describe_stacks()['Stacks'] }

    return self._stack

  def _process_stack(self, stack):
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
        return

      change_set_type = 'UPDATE'
    else:
      change_set_type = 'CREATE'

    v = self.cfn.validate_template(TemplateBody=stack.template_body)
    for cap in v.get('Capabilities', []):
      if cap not in stack.capabilities:
        reason = v.get('CapabilitiesReason', '(no reason provided)')
        raise ValidationError(
          'Required capability, {}, is missing in stack {}: {}'
          .format(cap, stack.name, reason))

    parameters = [
      {'ParameterKey': k, 'ParameterValue': v}
      for k, v in stack.parameters.items() ]

    tags = [{'Key': k, 'Value': v} for k, v in stack.tags.items()]
    tags.append({'Key': CONTENT_HASH_TAG, 'Value': content_hash})

    change_set = self.cfn.create_change_set(
      StackName=stack.name,
      TemplateBody=stack.template_body,
      Capabilities=stack.capabilities,
      ChangeSetType=change_set_type,
      ChangeSetName=content_hash,
      Parameters=parameters,
      Tags=tags,
    )

    return change_set_type, change_set['StackId'], change_set['Id']

  def process_stacks(self, managed_stacks):
    new_stacks = []
    updated_stacks = []
    orphaned_stacks = []

    unchanged_stacks = []
    unmanaged_stacks = []

    stack_actions = {
      None: unchanged_stacks,
      'CREATE': new_stacks,
      'UPDATE': updated_stacks,
    }

    change_sets = []
    for s in managed_stacks:
      change_set_type, stack_id, change_set_id = self._process_stack(s)

      stack_actions[change_set_type].append(s.name)
      change_sets.append((stack_id, change_set_id))

    for n, s in self.deployed_stacks.items():
      if not s.content_hash:
        unmanaged_stacks.append(n)
      elif not hasattr(s, 'is_outdated'):
        orphaned_stacks.append(n)

    return (
      change_sets or None,
      new_stacks or None,
      updated_stacks or None,
      orphaned_stacks or None,
      unmanaged_stacks or None)
