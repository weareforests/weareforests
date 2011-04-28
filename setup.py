#!/usr/bin/env python
# Copyright (c) 2010 Arjan Scherpenisse
# See LICENSE for details.

"""
WeAreForests installation script
"""

from setuptools import setup
import os
import sys
from twisted.python import procutils


setup(
    name = "WeAreForests",
    version = "0.4",
    author = "Arjan Scherpenisse",
    author_email = "arjan@scherpenisse.net",
    url = "http://scherpenisse.net/weareforests",
    description = "Telephony-based sound performance",
    packages = ['weareforests'],
    install_requires = [
    'Sparked>=0.10'
    ],
    classifiers = [
        "Framework :: Twisted",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Topic :: Communications",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities"
        ]
    )

