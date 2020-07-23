import argparse
import base64
import os
import re
import sys
import textwrap

from . import __version_info__
from . import aws
from . import cfn
from . import error
from . import markdown

from .model import Model


VALID_SESSION_NAME = re.compile(r'[\w+=,.@-]+')


def process_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--profile', help='Name of AWS configuration profile in ~/.aws/config')
    parser.add_argument('--default-region', help='Name of default AWS region')
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
        setups. Namely, it prevents stacks managed in other projects from being
        marked orphaned.''')
    parser.add_argument(
        '--target', action='append', help='''Add named target to list of targets to
        process. If no target is specified, then all configured targets are
        processed.''')
    parser.add_argument(
        '--region', action='append', help='''Add region to list of regions to be
        processed. If no region is specified, then all configured regions are
        processed.''')
    parser.add_argument(
        '--stack', action='append', help='''Add stack to list of stacks to be
        processed. If no stack is specified, then all configured stacks are
        processed.''')
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
    result = '{}+{}'.format(session_prefix, target_name)
    if project:
        result += '@{}'.format(project)
    return '-'.join(VALID_SESSION_NAME.findall(result))


def setup_session(target, session, session_prefix, project):
    if target.role:
        session = session.assume_role(
            role_arn=f'arn:aws:iam::{target.account}:role/{target.role}',
            session_name=_session_name(session_prefix, target.name, project),
            session_duration=15*60,   # seconds
        )
    return cfn.Session(
        session.cloudformation(region=target.region), project=project)


def _main():
    params = process_arguments()

    session = aws.Session(profile=params.profile, region=params.default_region)
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
        file=sys.stderr, flush=True)

    model = Model.from_targets_file(params.config_file)

    targets = list(model.single_region_targets(
        targets=params.target, regions=params.region, stacks=params.stack))

    for target in targets:
        print(target.header, file=sys.stderr, flush=True)

        target.cfn_session = setup_session(
            target, session, session_prefix, params.project)
        target.cfn_session.analyse_target(target)

        if not params.dry_run:
            target.cfn_session.prepare_change_sets(target)

        print(target, file=sys.stderr, flush=True)

    if params.markdown_summary:
        if not params.dry_run:
            for target in targets:
                target.cfn_session.wait_for_ready(target)

        print(markdown.summary(targets), end='', flush=True)


def main():
    try:
        _main()
    except error.Error as err:
        raise SystemExit(err)
