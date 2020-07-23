import os.path
import re

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from .dirloader import load_directory, normalize_key
from .loader import load_file
from .merge import deep_merge
from .schema.target import TargetConfigSchema
from .schema.template import CfnTemplateSchema
from .schema.stack import StackSchema


DEFAULT_ROLE_NAME = 'CfnReviewBot'

NOOP_CHANGESET_STATUS_REASON = '''The submitted information didn't contain ''' \
  '''changes. Submit different information to create a change set.'''


AccountId = str
Capability = str
ChangeSetId = str
IAMRoleName = str
Region = str
RegionList = Union[List[Region], Tuple[None]]
StackId = str
StackName = str
StackReference = Union[StackId, StackName]
TargetName = str


@dataclass
class Arn:
    partition: str
    service: str
    region: Region
    account: AccountId
    resource: str

    @classmethod
    def from_arn(cls, arn):
        return cls(*arn.split(':', 5)[1:])

    def __str__(s):
        return f'arn:{s.partition}:{s.service}:{s.region}:{s.account}:{s.resource}'


class ChangeSetType(Enum):
    CREATE = 'CREATE'
    UPDATE = 'UPDATE'


@dataclass
class ChangeSet:
    type: ChangeSetType
    stack: StackReference
    id: Optional[ChangeSetId] = None
    detail: Optional[Dict[str, Any]] = None

    @property
    def stack_id(self):
        return self.detail['StackId']

    @property
    def change_set_id(self):
        return self.detail['ChangeSetId']

    @property
    def region(self):
        return Arn.from_arn(self.change_set_id).region

    @property
    def url(self):
        return (
            f'https://{self.region}.console.aws.amazon.com/cloudformation/home'
            f'?region={self.region}'
            '#/stacks/changesets/changes'
            f'?stackId={self.detail["StackId"]}'
            f'&changeSetId={self.detail["ChangeSetId"]}'
        )

    @property
    def is_failed(self):
        return (
            self.detail is not None
            and self.detail['Status'] == 'FAILED')

    @property
    def is_noop(self):
        return (
            self.is_failed
            and self.detail['StatusReason'] == NOOP_CHANGESET_STATUS_REASON)


@dataclass
class Stack:
    name: StackName
    template: Dict[str, Any]
    capabilities: List[Capability] = field(default_factory=list)
    parameters: Dict[str, str] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)
    change_set: Optional[ChangeSet] = None


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
class TargetAnalysisResults:
    stack_summary: StackStats = field(default_factory=StackStats)
    new_stacks: List[StackReference] = field(default_factory=list)
    updated_stacks: List[StackReference] = field(default_factory=list)
    orphaned_stacks: List[StackReference] = field(default_factory=list)
    failed_stacks: List[StackReference] = field(default_factory=list)


TARGET_TYPE_RE = re.compile(
    r'\b([Dd][Ee][Vv]|[Pp][Rr][Ee]|[Pp][Rr][Oo][Dd]?)\b')

TARGET_TYPE_2_SWITCHROLE_COLOR = {
    None: '99BCE3',   # default
    'dev': 'B7CA9D',
    'pre': 'FAD791',
    'pro': 'F2B0A9',
    'prod': 'F2B0A9',
}


@dataclass
class SingleRegionTarget:
    name: TargetName
    account: Optional[AccountId] = None
    role: Optional[IAMRoleName] = None
    login_url: Union[bool, str, Dict[str, str]] = True
    region: Optional[Region] = None
    stacks: Dict[StackName, Stack] = field(default_factory=dict)
    analysis_results: Optional[TargetAnalysisResults] = None

    @property
    def login(self):
        if isinstance(self.login_url, bool):
            if self.login_url:
                return f'https://{self.account}.signin.aws.amazon.com/console'
            return

        if isinstance(self.login_url, str):
            return self.login_url

        if isinstance(self.login_url, dict):
            url = (
                'https://signin.aws.amazon.com/switchrole'
                f'?account={self.login_url["account"]}'
                f'&roleName={self.login_url["role-name"]}'
                f'&displayName={self.login_url.get("display-name") or self.name}')

            color = TARGET_TYPE_2_SWITCHROLE_COLOR[None]
            if 'color' in self.login_url:
                color = self.login_url['color']
            else:
                match = TARGET_TYPE_RE.search(self.name)
                if match:
                    target_type = match.group(0).lower()
                    color = TARGET_TYPE_2_SWITCHROLE_COLOR.get(target_type, color)
            url += f'&color={color}'

            return url

        return

    @property
    def change_sets(self):
        for s in self.stacks.values():
            if s.change_set is not None:
                yield s.change_set

    @property
    def header(self):
        return f'Target: {self.name} | {self.account} | {self.region}'

    def __str__(self):
        results = self.analysis_results

        lines = []

        if results is None:
            lines += ['Stacks: (not analysed)']
        else:
            lines += [f'Stacks: {results.stack_summary}']

            if results.orphaned_stacks:
                lines += [f'Orphaned stacks: {", ".join(results.orphaned_stacks)}']
            if results.failed_stacks:
                lines += [f'Failed stacks: {", ".join(results.failed_stacks)}']

            for change_set in self.change_sets:
                lines += [f'- {change_set.stack}']
                if change_set.type == ChangeSetType.CREATE:
                    lines[-1] += ' (NEW)'

                if change_set.id is None:
                    lines += ['  (change set was not created)']
                else:
                    lines += [f'  {change_set.id}']

            lines += ['']

        return '\n'.join(lines)


@dataclass
class Target:
    name: TargetName
    account: Optional[AccountId] = None
    role: Optional[IAMRoleName] = None
    login_url: Union[bool, str, Dict[str, str]] = True
    default_regions: RegionList = (None,)
    tags: Dict[str, str] = field(default_factory=dict)
    stacks: Dict[Region, Dict[StackName, Stack]] = field(default_factory=lambda: defaultdict(dict))


@dataclass
class Model:
    default_targets: List[TargetName] = field(default_factory=list)
    default_account: Optional[AccountId] = None
    default_role: Optional[IAMRoleName] = None
    default_login_url: Union[bool, str, Dict[str, str]] = True
    default_regions: RegionList = (None,)
    project_root: str = '.'
    stacks_root: str = 'stack'
    templates_root: str = 'template'
    tags: Dict[str, str] = field(default_factory=dict)
    targets: Dict[TargetName, List[Target]] = field(default_factory=dict)

    @classmethod
    def from_config(cls, config, project_root=None):
        if project_root is None:
            if hasattr(config, '__file__'):
                project_root = os.path.dirname(config.__file__)
            else:
                project_root = '.'

        project_root = os.path.abspath(project_root)
        stacks_root = os.path.normpath(
            os.path.join(project_root, config['stack-root']))
        templates_root = os.path.normpath(
            os.path.join(project_root, config['template-root']))

        model = Model(
            default_targets=config['default'],
            default_account=config.get('account-id'),
            default_role=config.get('role-name'),
            default_login_url=config['login-url'],
            default_regions=config['region'],
            project_root=project_root,
            stacks_root=stacks_root,
            templates_root=templates_root,
            tags=config['tag'],
        )

        for name, targets in config['target'].items():
            named_target = []
            model.targets[name] = named_target

            for target in targets:
                tags = {}
                tags.update(model.tags)
                tags.update(target['tag'])

                default_role = model.default_role
                if 'account-id' in target:
                    default_role = model.default_role or DEFAULT_ROLE_NAME

                named_target.append(Target(
                    name=name,
                    account=target.get('account-id', model.default_account),
                    role=target.get('role-name', default_role),
                    login_url=target.get('login-url', model.default_login_url),
                    default_regions=target.get('region', model.default_regions),
                    tags=tags,
                ))

        return model

    @classmethod
    def from_targets_file(cls, targets_filename):
        config = load_file(targets_filename, schema=TargetConfigSchema)
        model = cls.from_config(config)

        stacks = dict(load_directory(
            model.stacks_root, schema=StackSchema, drop_suffix='stack'))
        templates = dict(load_directory(
            model.templates_root, schema=CfnTemplateSchema))

        for stack_name, stack in stacks.items():
            stack.setdefault('name', stack_name)

            capabilities = stack['capability']
            parameters = stack['parameter']

            template = {}
            for template_reference in stack['template']:
                next_template = templates[normalize_key(template_reference)]
                template = deep_merge(template, next_template)

            for target_ref in stack.get('target', model.default_targets):
                target_name = target_ref
                regions = None
                if isinstance(target_ref, dict):
                    target_name = target_ref['name']
                    regions = target_ref['region']

                for target in model.targets[target_name]:
                    tags = {}
                    tags.update(target.tags)
                    tags.update(stack['tag'])

                    if regions is None:
                        regions = stack.get('region', target.default_regions)

                    for region in regions:
                        target.stacks[region][stack['name']] = Stack(
                            name=stack['name'],
                            capabilities=capabilities,
                            parameters=parameters,
                            tags=tags,
                            template=template,
                        )

        return model

    def single_region_targets(self, *, targets=None, regions=None, stacks=None):
        if targets:
            targets_iter = ((tn, self.targets[tn]) for tn in targets)
        else:
            targets_iter = self.targets.items()

        for name, named_target in targets_iter:
            for target in named_target:
                if regions:
                    regions_iter = ((r, target.stacks[r]) for r in regions)
                else:
                    regions_iter = target.stacks.items()

                for region, all_stacks in regions_iter:
                    if stacks:
                        all_stacks = {s: all_stacks[s] for s in stacks if s in all_stacks}

                    yield SingleRegionTarget(
                        name=name,
                        account=target.account,
                        role=target.role,
                        login_url=target.login_url,
                        region=region,
                        stacks=all_stacks)
