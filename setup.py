#!/usr/bin/env python

from setuptools import setup, find_packages

setup(name='autoCorrelator',
      version='',
      author='',
      author_email='',
      description='',
      long_description='',
      url='',
      package_dir={'': 'src'},
      packages=find_packages('src'),
      entry_points={
          'karabo.python_device.api_1': [
              'AutoCorrelator = autoCorrelator.AutoCorrelator:AutoCorrelator',
          ],
      },
      package_data={},
      requires=[],
      )

