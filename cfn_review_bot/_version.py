import collections
import datetime
import json
import os
import subprocess


EPOCH = '1'

BASEDIR = os.path.dirname(__file__)
PACKAGE_VERSION_FILE = os.path.join(BASEDIR, 'package-version.json')


VersionInfo = collections.namedtuple(
  'VersionInfo', ['epoch', 'version', 'git_revision'])

VersionInfo.package_version = property(
  lambda v: '{v.epoch}!{v.version}'.format(v=v))


def prepare_version_info_for_package():
  vi = _get_version_info_from_git()
  with open(PACKAGE_VERSION_FILE, mode='w') as f:
    json.dump(vi._asdict(), f, ensure_ascii=True, indent=2, sort_keys=True)
  return vi


def _get_version_info_from_package():
  with open(PACKAGE_VERSION_FILE) as f:
    data = json.load(f)
  return VersionInfo(**data)


def _get_git_timestamp():
  git_output = subprocess.check_output(
    'git log -1 --date=unix --format=format:%cd'.split(),
    stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
  return datetime.datetime.utcfromtimestamp(int(git_output))


def _get_git_revision():
  git_output = subprocess.check_output(
    'git describe --always --abbrev=12 --dirty=.dirty'.split(),
    stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
  return git_output.strip().decode()


def _get_version_info_from_git():
  return VersionInfo(
    epoch=EPOCH,
    version=_get_git_timestamp().strftime('%Y%m%d.%H%M%S'),
    git_revision=_get_git_revision())


def _get_version_info():
  try:
    return _get_version_info_from_package()
  except FileNotFoundError:
    pass

  return _get_version_info_from_git()
