#!/usr/bin/env python
"""Distutils setup file"""

import ez_setup
ez_setup.use_setuptools()
from setuptools import setup

# Metadata
PACKAGE_NAME = "ObjectRoles"
PACKAGE_VERSION = "0.7"
PACKAGES = ['peak', 'peak.util']

def get_description():
    # Get our long description from the documentation
    f = file('README.txt')
    lines = []
    for line in f:
        if not line.strip():
            break     # skip to first blank line
    for line in f:
        if line.startswith('.. contents::'):
            break     # read to table of contents
        lines.append(line)
    f.close()
    return ''.join(lines)

setup(
    name=PACKAGE_NAME,
    version=PACKAGE_VERSION,
    description="Separation of concerns (basic AOP) using 'role' adapters",
    long_description = open('README.txt').read(), # get_description(),
    install_requires=['DecoratorTools>=1.5'],
    author="Phillip J. Eby",
    author_email="peak@eby-sarna.com",
    license="PSF or ZPL",
    url="http://www.python.org/pypi/ObjectRoles",
    test_suite = 'peak.util.roles',
    packages = PACKAGES,
    namespace_packages = PACKAGES,
)

