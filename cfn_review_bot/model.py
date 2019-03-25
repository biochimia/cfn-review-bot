import os.path

from .dirloader import load_directory, normalize_key
from .loader import load_file
from .merge import deep_merge
from .schema.target import TargetConfigSchema
from .schema.template import TemplateSchema
from .schema.stack import StackSchema


def process_target_config(target_config):
  default_region = target_config['region']
  default_role_name = target_config['role-name']

  global_tags = target_config['tag']

  all_targets_expanded = {}
  for name, targets in target_config['target'].items():
    targets_expanded = []
    all_targets_expanded[name] = targets_expanded

    for target in targets:
      target_region = target.get('region', default_region)
      for region in target_region:
        tags = {}
        tags.update(global_tags)
        tags.update(target['tag'])

        targets_expanded.append({
          'account-id': target['account-id'],
          'role-name': target.get('role-name', default_role_name),
          'region': region,
          'tag': tags,
          'stack': {},
        })

  target_config['target'] = all_targets_expanded

  basedir = os.path.dirname(target_config.__file__)

  target_config['stack-root'] = os.path.normpath(
    os.path.join(basedir, target_config['stack-root']))
  target_config['template-root'] = os.path.normpath(
    os.path.join(basedir, target_config['template-root']))

  return target_config


def load(config_file):
  targets = load_file(config_file, schema=TargetConfigSchema)
  targets = process_target_config(targets)

  templates = dict(
    load_directory(targets['template-root'], schema=TemplateSchema))
  stacks = dict(load_directory(
    targets['stack-root'], schema=StackSchema, drop_suffix='stack'))

  default_target_names = targets['default']
  all_targets = targets['target']

  for stack_name, stack in stacks.items():
    capabilities = stack['capability']
    parameters = stack['parameter']

    template = {}
    for template_reference in stack['template']:
      cur_template = templates[normalize_key(template_reference)]
      template = deep_merge(template, cur_template)

    for tn in stack.get('target', default_target_names):
      for target in all_targets[tn]:
        aggregated_tags = {}
        aggregated_tags.update(target['tag'])
        aggregated_tags.update(stack['tag'])

        target['stack'][stack_name] = {
          'name': stack_name,
          'template': template,
          'capabilities': capabilities,
          'parameters': parameters,
          'tags': aggregated_tags,
        }

  return targets
