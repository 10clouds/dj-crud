#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name='django-crud',
    version='0.1',
    description=('CRUD application provides shortcuts and ready to use '
                 'templates for dynamic CRUD views'),
    author='10clouds',
    packages=find_packages(),
    include_package_data=True,
)
