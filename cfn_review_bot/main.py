import argparse
import base64
import os
import re
import textwrap

from . import __version_info__
from . import aws
from . import cfn
from . import error
from . import loader
from . import model


VALID_SESSION_NAME = re.compile(r'[\w+=,.@-]+')


def process_arguments():
  parser = argparse.ArgumentParser()
  parser.add_argument(
    '--profile', help='Name of AWS configuration profile in ~/.aws/config')
  parser.add_argument('--region', help='Name of default AWS region')
  parser.add_argument(
    '--session-prefix', help='''Prefix for the session name to use when assuming
    IAM roles. If not specified, this defaults to a random string. This prefix
    will be combined with the name of the different deployment targets to
    produce the session name.''')
  parser.add_argument(
    '--config-file', default='cfn-targets.yaml', help='''Configuration file that
    defines deployment targets''')
  parser.add_argument(
    '--project', default='', help='''A project identifier. This can be used to
    distinguish CloudFormation stacks managed by independent cfn-review-bot
    setups. Namely, it stacks managed in other projects from being marked
    orphaned.''')
  parser.add_argument(
    '--dry-run', '-n', action='store_true', help='''Evaluate targets, and
    validate stacks, but skip creation of change-sets''')

  return parser.parse_args()


def _default_session_prefix():
  return base64.b64encode(os.urandom(9), b'.-').decode('ascii')

def _session_name(session_prefix, target_name, project):
  result = '{}+{}'.format(session_prefix, target_name, project)
  if project:
    result += '@{}'.format(project)
  return '-'.join(VALID_SESSION_NAME.findall(result))


def process_single_target(
  sess, session_prefix, target_name, target_config, *, project, dry_run=False):

  account_id = target_config['account-id']
  role_name = target_config['role-name']
  region = target_config['region']
  stacks = target_config['stack']

  if 'role-name' in target_config:
    sess = sess.assume_role(
      role_arn='arn:aws:iam::{}:role/{}'.format(account_id, role_name),
      session_name=_session_name(session_prefix, target_name, project),
      session_duration=15*60, # seconds
    )

  tgt = cfn.Target(sess.cloudformation(region=region), project=project)
  target_results = tgt.process_stacks(stacks.values(), dry_run=dry_run)

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
    updated_summary = '{} updated'.format(counts['updated'])
    if counts['adopted']:
      updated_summary += ' ({} adopted)'.format(counts['adopted'])
    count_summary.append(updated_summary)
  if counts['orphaned']:
    count_summary.append('{} orphaned'.format(counts['orphaned']))

  if not count_summary:
    count_summary = ['unchanged']

  print(
    'Stacks: {summary} (total: {c[total]}, unmanaged: {c[unmanaged]})'
    .format(summary=' | '.join(count_summary), c=counts))

  if target_results['change-set-id']:
    print('Change sets:')
    for csid in target_results['change-set-id']:
      print('- {}'.format(csid))

  print()


def _main():
  params = process_arguments()

  session = aws.Session(profile=params.profile, region=params.region)
  session_prefix = params.session_prefix or _default_session_prefix()

  print(textwrap.dedent(
    '''
    cfn-review-bot (version {vi.version}, git {vi.git_revision})

    * Project:              {p.project}
    * Config:               {p.config_file}
    * AWS profile:          {s.profile_name}
    * Default region:       {s.region_name}
    * Session name prefix:  {session_prefix}
    ''')
    .lstrip()
    .format(
      p=params,
      s=session,
      session_prefix=session_prefix,
      vi=__version_info__))

  full_model = model.load(params.config_file)

  for target_name, targets in full_model['target'].items():
    for target in targets:
      stacks = target['stack']
      if not stacks:
        continue

      target_results = process_single_target(
        session,
        session_prefix,
        target_name,
        target,
        project=params.project,
        dry_run=params.dry_run)

      print_target_results(target_results)


def main():
  try:
    _main()
  except error.Error as err:
    raise SystemExit(err)
