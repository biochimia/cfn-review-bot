import setuptools
import subprocess

from datetime import datetime

from cfn_review_bot import version


def get_version():
  return '{epoch}!{time:%Y%m%d.%H%M%S}.g{revision}'.format(
    epoch=version.epoch, time=get_git_timestamp(), revision=get_git_revision())


def get_git_timestamp():
  return datetime.utcfromtimestamp(int(subprocess.check_output(
    ['git', 'log', '-1', '--date=unix', '--format=format:%cd'],
    stderr=subprocess.DEVNULL)))


def get_git_revision():
  return subprocess.check_output(
    ['git', 'describe', '--always', '--abbrev=12', '--dirty=.dirty'],
    stderr=subprocess.DEVNULL).strip().decode()


def get_long_description():
  with open('README.md') as readme:
    return readme.read()


def get_requirements():
  with open('requirements.txt') as requirements:
    for line in requirements:
      requires = line.partition('#')[0]
      requires = line.strip()
      if requires:
        yield requires


setuptools.setup(
  name='cfn-review-bot',
  version=get_version(),
  author=u'Jo\u00e3o Abecasis',
  author_email='joao@abecasis.name',
  description='CLI to manage CloudFormation stacks',
  long_description=get_long_description(),
  long_description_content_type='text/markdown',
  url='https://github.com/biochimia/cfn-review-bot',
  classifiers=[
    'Programming Language :: Python :: 3',
    'License :: OSI Approved :: Apache Software License',
    'Operating System :: OS Independent',
  ],
  packages=setuptools.find_packages(),
  data_files=[('requirements', ['requirements.txt'])],
  install_requires=list(get_requirements()),
  python_requires='>=3.7',
  entry_points={
    'console_scripts': [
      'cfn-review-bot=cfn_review_bot.main:main',
    ]
  },
)
