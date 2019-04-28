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
  account_id = target_config['account-id']
  role_name = target_config['role-name']
  region = target_config['region']
  stacks = target_config['stack']

  if 'role-name' in target_config:
    sess = sess.assume_role(
      role_arn='arn:aws:iam::{}:role/{}'.format(account_id, role_name),
      session_name='{}+{}'.format(session_name, target_name),
      session_duration=15*60, # seconds
    )

  tgt = cfn.Target(sess.cloudformation(region=region))
  target_results = tgt.process_stacks(
    cfn.Stack(**stack) for stack in stacks.values())

  target_results.update({
    'name': target_name,
    'account-id': account_id,
    'region': region,
  })

  return target_results


def print_target_results(target_results):
  print(
    'Target: {t[name]} | {t[account-id]} | {t[region]}'
    .format(t=target_results))

  if target_results['orphaned-stack']:
    print(
      'Orphaned stacks: {}'
      .format(', '.join(target_results['orphaned-stack'])))

  counts = target_results['stack-count']
  count_summary = []
  if counts['new']:
    count_summary.append('{} new'.format(counts['new']))
  if counts['updated']:
    count_summary.append('{} updated'.format(counts['updated']))
  if counts['orphaned']:
    count_summary.append('{} orphaned'.format(counts['orphaned']))

  if not count_summary:
    count_summary = ['unchanged']

  print(
    'Stacks: {summary} (total: {c[total]}, unmanaged: {c[unmanaged]})'
    .format(summary=' | '.join(count_summary), c=counts))

  print('Change sets:')
  for csid in target_results['change-set-id']:
    print('- {}'.format(csid))

  print()


def _main():
  params = process_arguments()

  session = aws.Session(profile=params.profile, region=params.region)
  full_model = model.load(params.config_file)

  session_name = params.session_name or str(uuid.uuid4())

  for target_name, targets in full_model['target'].items():
    for target in targets:
      stacks = target['stack']
      if not stacks:
        continue

      target_results = process_single_target(
        session, session_name, target_name, target)
      print_target_results(target_results)


def main():
  try:
    _main()
  except error.Error as err:
    raise SystemExit(err)
