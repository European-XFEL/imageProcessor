#!/usr/bin/env python

from setuptools import setup, find_packages

setup(name='imageProcessor',
      version='',
      author='',
      author_email='',
      description='',
      long_description='',
      url='',
      package_dir={'': 'src'},
      packages=find_packages('src'),
      entry_points={
          'karabo.bound_device': [
              'ImageApplyMask = imageProcessor.ImageApplyMask:ImageApplyMask',
              'ImageApplyRoi = imageProcessor.ImageApplyRoi:ImageApplyRoi',
              'ImageAverager = imageProcessor.ImageAverager:ImageAverager',
              'ImageProcessor = imageProcessor.ImageProcessor:ImageProcessor',
          ],
          'karabo.middlelayer_device': [
              'ImageToSpectrum = imageProcessor.ImageToSpectrum:ImageToSpectrum'
          ],
      },
      package_data={},
      requires=[],
      )

