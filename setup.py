#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import find_packages, setup

with open('README.md') as readme_file:
    readme = readme_file.read()

setup(
    name='observation-execution-tool',
    version="2.4.2",
    description="This project contains the code for the Observation Execution Tool, the application which provides high-level scripting facilities and a high-level scripting UI for the SKA.",
    long_description=readme + '\n\n',
    author="Your Name",
    author_email='stewart.williams@stfc.ac.uk',
    url='https://github.com/ska-telescope/observation-execution-tool',
    packages=find_packages(),
    entry_points={
        'console_scripts': ['oet=oet.procedure.application.restclient:main']
    },
    package_dir={'observation-execution-tool': 'oet'},
    include_package_data=True,
    license="BSD license",
    zip_safe=False,
    keywords='ska_observation_execution_tool',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    test_suite='tests',
    install_requires=[
        'cdm-shared-library',
        'fire',
        'flask',
        'pytango',
        'requests',
        'tabulate',
        'skuid',
        'ska-project-data-model-library',
        'ska-logging',
        'pypubsub',
        'tblib',
        'sseclient'
    ],
    setup_requires=[
        # dependency for `python setup.py test`
        'pytest-runner',
        # dependencies for `python setup.py build_sphinx`
        'sphinx',
        'recommonmark'
    ],
    tests_require=[
        'pytest',
        'pytest-cov',
        'pytest-json-report',
        'pycodestyle',
        'requests-mock'
    ],
    extras_require={
        'dev': ['prospector[with_pyroma]', 'yapf', 'isort']
    }
)
