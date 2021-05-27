#!/usr/bin/env python
from os.path import dirname, join, realpath

from setuptools import find_packages, setup

ROOT_FOLDER = dirname(realpath(__file__))
VERSION_FILE_PATH = join(
    ROOT_FOLDER, 'src', 'simpleImageProcessor', '_version.py')

try:
    from karabo.packaging.versioning import device_scm_version
    scm_version = device_scm_version(ROOT_FOLDER, VERSION_FILE_PATH)
except ImportError:
    # compatibility with karabo versions earlier than 2.10
    scm_version = {'write_to': VERSION_FILE_PATH}


setup(name='simpleImageProcessor',
      use_scm_version=scm_version,
      author='',
      author_email='',
      description='',
      long_description='',
      url='',
      package_dir={'': 'src'},
      packages=find_packages('src'),
      entry_points={
          'karabo.bound_device': [
              'SimpleImageProcessor = simpleImageProcessor.SimpleImageProcessor:SimpleImageProcessor',
          ],
      },
      package_data={},
      requires=[],
      )
