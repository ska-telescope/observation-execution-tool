#!/usr/bin/env python
# -*- coding: utf-8 -*-

import setuptools

with open('README.md') as readme_file:
    readme = readme_file.read()

setuptools.setup(
    name='observation-execution-tool',
    version="2.9.3",
    description="This project contains the code for the Observation Execution Tool, the application which provides high-level scripting facilities and a high-level scripting UI for the SKA.",
    long_description=readme + '\n\n',
    author="Stewart Williams",
    author_email='stewart.williams@stfc.ac.uk',
    url='https://github.com/ska-telescope/observation-execution-tool',
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    entry_points={
        'console_scripts': ['oet=oet.procedure.application.restclient:main']
    },
    include_package_data=True,
    license="BSD license",
    zip_safe=False,
    keywords='ska_observation_execution_tool',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.7',
    ],
    test_suite='tests/unit',
    install_requires=[
        'fire',
        'flask',
        'jsonpickle',
        'pypubsub',
        'pytango',
        'requests',
        'ska-logging',
        'skuid',
        'sseclient',
        'tabulate',
        'tblib',
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
