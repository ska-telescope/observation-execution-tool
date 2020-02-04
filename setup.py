#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_namespace_packages

with open('README.md') as readme_file:
    readme = readme_file.read()

setup(
    name='observation-execution-tool',
    version="0.3.0",
    description="",
    long_description=readme + '\n\n',
    author="Your Name",
    author_email='stewart.williams@stfc.ac.uk',
    url='https://github.com/ska-telescope/observation-execution-tool',
    packages=find_namespace_packages(include=['oet.*']),
    entry_points = {
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
    install_requires=['pytango', 'cdm-shared-library'],
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
    ],
    extras_require={
        'dev':  ['prospector[with_pyroma]', 'yapf', 'isort']
    }
)
