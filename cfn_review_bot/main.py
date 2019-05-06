import argparse
import base64
import os
import re
import sys
import textwrap

from dataclasses import dataclass

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
    '--target', help='''A comma-separated list of targets to process. If not
    specified, all targets defined in the config file are processed.''')
  parser.add_argument(
    '--markdown-summary', action='store_true', help='''Print a
    markdown-formatted summary of modified stacks and created change sets to
    standard output.''')
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


@dataclass
class TargetResults:
  target: cfn.Target
  name: str
  account: str
  region: str
  results: cfn.ProcessStacksResult

  def wait_for_ready(self):
    for change_set in self.results.change_sets:
      self.target.wait_for_ready(change_set)

  def __str__(self):
    lines = [f'Target: {self.name} | {self.account} | {self.region}']
    lines += [f'Stacks: {self.results.stack_summary}']
    if self.results.orphaned_stacks:
      lines += [f'Orphaned stacks: {", ".join(self.results.orphaned_stacks)}']

    if self.results.change_sets:
      for change_set in self.results.change_sets:
        lines += [f'- {change_set.stack}']
        if change_set.type == cfn.ChangeSetType.CREATE:
          lines[-1] += ' (NEW)'

        if change_set.id is None:
          lines += ['  (change set was not created)']
        else:
          lines += [f'  {change_set.id}']

    lines += ['']
    return '\n'.join(lines)


def process_single_target(
  sess,
  session_prefix,
  target_name,
  *,
  account_id,
  stacks,
  project,
  region=None,
  role_name=None,
  dry_run=False):

  if role_name:
    sess = sess.assume_role(
      role_arn='arn:aws:iam::{}:role/{}'.format(account_id, role_name),
      session_name=_session_name(session_prefix, target_name, project),
      session_duration=15*60, # seconds
    )

  tgt = cfn.Target(sess.cloudformation(region=region), project=project)
  target_results = tgt.process_stacks(stacks.values(), dry_run=dry_run)

  return TargetResults(tgt, target_name, account_id, region, target_results)


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
      vi=__version_info__),
    file=sys.stderr)

  full_model = model.load(params.config_file)
  if params.target is None:
    all_targets = full_model['target'].items()
  else:
    target_names = (tn.strip() for tn in params.target.split(','))
    all_targets = ((tn, full_model['target'].get(tn, [])) for tn in target_names)

  results = []
  for target_name, targets in all_targets:
    for target_config in targets:
      for region, stacks in target_config['stack'].items():
        target_results = process_single_target(
          session,
          session_prefix,
          target_name,
          account_id=target_config['account-id'],
          role_name=target_config.get('role-name'),
          region=region,
          stacks=stacks,
          project=params.project,
          dry_run=params.dry_run)

        results.append(target_results)
        print(target_results, file=sys.stderr)

  if not params.dry_run:
    for target_results in results:
      target_results.wait_for_ready()

  if params.markdown_summary:
    from . import markdown
    print(markdown.summary(results), end='', flush=True)


def main():
  try:
    _main()
  except error.Error as err:
    raise SystemExit(err)
