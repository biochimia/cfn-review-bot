'''
Automated package versioning from source control.

Because life is too short to fret over releases and version numbers, every
revision in source control can, potentially, be a release. This module uses the
revision's timestamp as the package version.

As release numbers are generated automatically from version control, the
variable `EPOCH` may be incremented to signal major (backwards incompatible)
changes to the package. (In PEP 440, the epoch is specified as a way to support
changing a package's versioning scheme. We abuse it here as a replacement for
major version numbers in semantic versioning.)

The class `VersionInfo` is a named tuple `(epoch, version, git_revision)`, that
provides the computed property `package_version` as a string.

The function `get_version_info()` checks for the presense of the file
`package-version.json` in the package, and returns version information from
there, if it is available. If the file is missing, source control (i.e., git) is
queried, instead.

Packaging scripts should call `prepare_version_info_for_package()` to query
source control for version information, and generate `package-version.json`.
This file should be included in released packages.

Note: as the source control system may not enforce a monotonically increasing
revision timestamp, care should be taken to avoid a regression of the package
version. When using `git`, a development model based on feature branches where a
merge commit is created at the time a feature is accepted into the main branch
can provide this invariant.
'''

import collections
import datetime
import json
import os
import subprocess


EPOCH = '1'

BASEDIR = os.path.dirname(__file__)
PACKAGE_VERSION_FILE = os.path.join(BASEDIR, 'package-version.json')


class VersionInfo(
  collections.namedtuple('VersionInfo', ['epoch', 'version', 'git_revision'])):

  @property
  def package_version(self):
    return '{s.epoch}!{s.version}'.format(s=self)


def _get_git_revision():
  git_output = subprocess.check_output(
    'git describe --always --abbrev=12 --dirty=.dirty'.split(),
    stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
  return git_output.strip().decode()


def _get_git_timestamp():
  git_output = subprocess.check_output(
    'git log -1 --date=unix --format=format:%cd'.split(),
    stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
  return datetime.datetime.utcfromtimestamp(int(git_output))


def get_version_info():
  try:
    return _get_version_info_from_package()
  except FileNotFoundError:
    pass
  return _get_version_info_from_git()


def _get_version_info_from_git():
  return VersionInfo(
    epoch=EPOCH,
    version=_get_git_timestamp().strftime('%Y%m%d.%H%M%S'),
    git_revision=_get_git_revision())


def _get_version_info_from_package():
  with open(PACKAGE_VERSION_FILE) as f:
    data = json.load(f)
  return VersionInfo(**data)


def prepare_version_info_for_package():
  vi = _get_version_info_from_git()
  with open(PACKAGE_VERSION_FILE, mode='w') as f:
    json.dump(vi._asdict(), f, ensure_ascii=True, indent=2, sort_keys=True)
  return vi
