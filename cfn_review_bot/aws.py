import os

import boto3.session
import botocore
import botocore.credentials
import botocore.exceptions


# Credentials cache is shared with awscli
AWSCLI_CACHE_DIR = os.path.expanduser('~/.aws/cli/cache')
DEFAULT_SESSION = None


class _AssumeRoleProvider:
  METHOD = 'assume-role'

  def __init__(self, fetcher):
    self._fetcher = fetcher

  def load(self):
    return botocore.credentials.DeferredRefreshableCredentials(
      self._fetcher.fetch_credentials, self.METHOD)


class Session:
  def __init__(self, *, core_session=None, profile=None, region=None):
    self._services = {}
    self._session = boto3.session.Session(
      region_name=region,
      profile_name=profile,
      botocore_session=core_session,
    )
    self._core_session = self._session._session

    if core_session is None:
      cred_chain = self._core_session.get_component('credential_provider')
      provider = cred_chain.get_provider('assume-role')
      provider.cache = botocore.credentials.JSONFileCache(AWSCLI_CACHE_DIR)

  # Adapted from:
  # https://github.com/boto/botocore/issues/761#issuecomment-426037853
  def assume_role(self, *, role_arn, session_duration=None, session_name=None):

    if session_duration is None:
      session_duration = 15 * 60
    if session_name is None:
      session_name = __name__

    no_credentials_cache = None
    fetcher = botocore.credentials.AssumeRoleCredentialFetcher(
      self._core_session.create_client, self._core_session.get_credentials(),
      role_arn, extra_args={
        'RoleSessionName': session_name,
        'DurationSeconds': session_duration,
      }, cache=no_credentials_cache)

    core_session = botocore.session.Session()
    core_session.register_component(
      'credential_provider',
      botocore.credentials.CredentialResolver([_AssumeRoleProvider(fetcher)]))

    return Session(region=self._session.region_name, core_session=core_session)

  def get_service(self, service_name, *, region=None):
    if region is None:
      region = self._session.region_name
    key = (service_name, region)

    try:
      return self._services[key]
    except KeyError:
      pass

    service = self._core_session.create_client(
      service_name, region_name=region)
    self._services[key] = service
    return service

  def __getattr__(self, service_name):
    return Service(self, service_name)
    return Service(self.get_service(service_name))


class Service:
  def __init__(self, session, service_name, *, region=None):
    self.session = session
    self.service_name = service_name
    self.region = region

  def __call__(self, *, region):
    return Service(self.session, self.service_name, region=region)

  def __getattr__(self, method_name):
    service = self.session.get_service(self.service_name, region=self.region)
    native_method_name = botocore.xform_name(method_name)

    if service.can_paginate(native_method_name):
      paginator = service.get_paginator(native_method_name)
      def paginate_method(*args, **kwargs):
        return paginator.paginate(*args, **kwargs).build_full_result()
      paginate_method.__name__ = '{}:paginated'.format(native_method_name)
      return paginate_method

    return getattr(service, native_method_name)
