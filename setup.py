import setuptools

import cfn_review_bot._version


version_info = cfn_review_bot._version.prepare_version_info_for_package()


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
  version=version_info.package_version,
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
  package_data={
    'cfn_review_bot': [cfn_review_bot._version.PACKAGE_VERSION_FILE],
  },
  data_files=[('requirements', ['requirements.txt'])],
  install_requires=list(get_requirements()),
  python_requires='>=3.7',
  entry_points={
    'console_scripts': [
      'cfn-review-bot=cfn_review_bot.main:main',
    ],
  },
)
