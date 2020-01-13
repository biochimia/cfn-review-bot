import datetime
import time

from . import error
from . import loader

from .canonical import canonical_hash
from .merge import deep_merge
from .model import (
    ChangeSet, ChangeSetType, TargetAnalysisResults)


CFN_METADATA_PARAMETER = 'ReviewBotMetadata'


class ValidationError(error.Error):
    pass


class TimeoutError(error.Error):
    pass


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


class Session:
    metadata_parameter = CFN_METADATA_PARAMETER

    def __init__(self, cfn, *, project):
        self.cfn = cfn
        self.project = project

    @property
    def metadata_suffix(self):
        return f'@{self.project}' if self.project else ''

    @property
    def deployed_stacks(self):
        try:
            return self._stack
        except AttributeError:
            pass

        self._stack = {
            stack['StackName']: DeployedStack(
                stack,
                metadata_parameter=self.metadata_parameter,
                metadata_suffix=self.metadata_suffix)
            for stack in self.cfn.describe_stacks()['Stacks']
        }

        return self._stack

    def get_content_hash(self, stack):
        canonical_content = dict(
            template=stack.template,
            parameters=stack.parameters,
            tags=stack.tags)
        if self.project:
            canonical_content['project'] = self.project
        return canonical_hash(canonical_content)

    def prepare_change_sets(self, target):
        for stack_name, stack in target.stacks.items():
            if stack.change_set is None:
                continue

            template_body = self.prepare_template_body(stack)
            stack.change_set = self.prepare_change_set(
                stack, stack.change_set.type, template_body)

    def analyse_single_stack(self, stack):
        deployed = self.deployed_stacks.get(stack.name)
        if (not deployed
                or deployed.status == 'REVIEW_IN_PROGRESS'):
            return ChangeSet(ChangeSetType.CREATE, stack.name)

        if deployed.status == 'ROLLBACK_COMPLETE':
            raise ValidationError(
                f'Stack {stack.name} with ROLLBACK_COMPLETE status needs to be deleted '
                f'before it can be recreated.')

        deployed.is_outdated = (
            self.get_content_hash(stack) != deployed.content_hash)
        if deployed.is_outdated:
            return ChangeSet(ChangeSetType.UPDATE, stack.name)

    def prepare_template_body(self, stack):
        return loader.dump_yaml(
            deep_merge(
                dict(Parameters={self.metadata_parameter: dict(Type='String')}),
                stack.template),
            stream=None)

    def validate_template_body(self, stack, template_body):
        v = self.cfn.validate_template(TemplateBody=template_body)
        for cap in v.get('Capabilities', []):
            if cap not in stack.capabilities:
                reason = v.get('CapabilitiesReason', '(no reason provided)')
                raise ValidationError(
                    'Required capability, {}, is missing in stack {}: {}'
                    .format(cap, stack.name, reason))

    def prepare_change_set(self, stack, change_set_type, template_body):
        content_hash = self.get_content_hash(stack)

        parameters = [dict(
            ParameterKey=self.metadata_parameter,
            ParameterValue=content_hash + self.metadata_suffix)]
        parameters.extend(
            dict(ParameterKey=k, ParameterValue=v)
            for k, v in stack.parameters.items())

        tags = [dict(Key=k, Value=v) for k, v in stack.tags.items()]

        change_set = self.cfn.create_change_set(
            StackName=stack.name,
            TemplateBody=template_body,
            Capabilities=stack.capabilities,
            ChangeSetType=change_set_type.value,
            ChangeSetName=content_hash,
            Parameters=parameters,
            Tags=tags)

        stack_id = change_set['StackId']
        change_set_id = change_set['Id']
        return ChangeSet(change_set_type, stack_id, change_set_id)

    def analyse_target(self, target):
        result = TargetAnalysisResults()
        for stack_name, stack in target.stacks.items():
            stack.change_set = self.analyse_single_stack(stack)
            if stack.change_set is None:
                continue

            if stack.change_set.type == ChangeSetType.CREATE:
                result.stack_summary.total += 1
                result.stack_summary.new += 1
            elif stack.change_set.type == ChangeSetType.UPDATE:
                result.stack_summary.updated += 1

            template_body = self.prepare_template_body(stack)
            self.validate_template_body(stack, template_body)

        for stack_name, stack in self.deployed_stacks.items():
            if stack.status == 'REVIEW_IN_PROGRESS':
                # Not yet a stack, counted as NEW if a CREATE change set was created.
                continue

            if stack.status == 'ROLLBACK_COMPLETE':
                # Not a stack, creation failed. Should be deleted.
                result.failed_stacks += [stack_name]
                continue

            result.stack_summary.total += 1

            if hasattr(stack, 'is_outdated'):
                # Managed (or now adopted) stack
                if not stack.content_hash:
                    result.stack_summary.adopted += 1
                continue

            if stack.content_hash:
                result.stack_summary.orphaned += 1
                result.orphaned_stacks += [stack_name]
            elif stack.is_unmanaged:
                result.stack_summary.unmanaged += 1

        target.analysis_results = result

    def wait_for_ready(self, target):
        for change_set in target.change_sets:
            self.wait_for_change_set(change_set)

    def wait_for_change_set(self, change_set: ChangeSet):
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
