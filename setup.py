import setuptools


version = '0.1.0'

with open('README.md') as readme:
    long_description = readme.read()

install_requires = []
with open('requirements.txt') as requirements:
    for line in requirements:
        requires = line.partition('#')[0]
        requires = line.strip()
        if requires:
            install_requires.append(requires)

setuptools.setup(
    name='cfn-review-bot',
    version=version,
    author=u'Jo\u00e3o Abecasis',
    author_email='joao@abecasis.name',
    description='CLI to manage CloudFormation stacks',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/biochimia/cfn-review-bot',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
    ],
    packages=setuptools.find_packages(),
    data_files=[('requirements', ['requirements.txt'])],
    install_requires=install_requires,
    python_requires='>=3.7',
    entry_points={
        'console_scripts': [
            'cfn-review-bot=cfn_review_bot.__main__:main',
        ]
    },
)
