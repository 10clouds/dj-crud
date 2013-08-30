#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name='django-crud',
    version='0.1.2',
    description=(
        'CRUD application provides shortcuts and ready to use templates for '
        'dynamic CRUD views'
    ),
    author='10clouds',
    packages=find_packages(),
    include_package_data=True,
    namespace_packages=['tenclouds'],
    url='https://github.com/10clouds/dj-crud',
    download_url='https://github.com/10clouds/dj-crud/tarball/master',
    install_requires=[
        'django-tastypie'
    ],
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
