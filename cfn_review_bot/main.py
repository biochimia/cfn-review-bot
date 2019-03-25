import argparse
import uuid

from . import aws
from . import cfn
from . import error
from . import loader
from . import model


def process_arguments():
  parser = argparse.ArgumentParser()
  parser.add_argument('--profile')
  parser.add_argument('--region')
  parser.add_argument('--session-name')
  parser.add_argument('--config-file', default='cfn-targets.yaml')

  return parser.parse_args()


def process_single_target(sess, session_name, target_name, target_config):
  if 'role-name' in target_config:
    sess = sess.assume_role(
      role_arn='arn:aws:iam::{}:role/{}'.format(
        target_config['account-id'], target_config['role-name']),
      session_name='{}+{}'.format(session_name, target_name),
      session_duration=15*60, # seconds
    )

  region = target_config['region']
  stacks = target_config['stack']

  tgt = cfn.Target(sess.cloudformation(region=region))

  change_sets, new, updated, orphaned, unmanaged = tgt.process_stacks(
    cfn.Stack(**stack) for stack in stacks.values())

  if new:
    print('New stacks:', new)
  if updated:
    print('Updated stacks:', updated)
  if orphaned:
    print('Orphaned stacks:', orphaned)
  if unmanaged:
    print('Unmanaged stacks:', len(unmanaged))

  print('Change sets:', change_sets)


def _main():
  params = process_arguments()

  session = aws.Session(profile=params.profile, region=params.region)
  full_model = model.load(params.config_file)

  session_name = params.session_name or str(uuid.uuid4())

  for target_name, targets in full_model['target'].items():
    print('***  {}  ***'.format(target_name))
    for target in targets:
      stacks = target['stack']
      if not stacks:
        continue
      process_single_target(session, session_name, target_name, target)


def main():
  try:
    _main()
  except error.Error as err:
    raise SystemExit(err)
