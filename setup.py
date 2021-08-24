#!/usr/bin/env python
import shutil
from os.path import dirname, join, realpath

from setuptools import find_packages, setup

ROOT_FOLDER = dirname(realpath(__file__))
VERSION_FILE_PATH = join(ROOT_FOLDER, '_version.py')

try:
    from karabo.packaging.versioning import device_scm_version
    scm_version = device_scm_version(ROOT_FOLDER, VERSION_FILE_PATH)
except ImportError:
    # compatibility with karabo versions earlier than 2.10
    scm_version = {'write_to': VERSION_FILE_PATH}



setup(name='imageProcessor',
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
              'ImageApplyMask = imageProcessor.ImageApplyMask:ImageApplyMask',
              'ImageApplyRoi = imageProcessor.ImageApplyRoi:ImageApplyRoi',
              'ImageAverager = imageProcessor.ImageAverager:ImageAverager',
              'ImageBackgroundSubtraction = imageProcessor.ImageBackgroundSubtraction:ImageBackgroundSubtraction',
              'ImageCrosshair = imageProcessor.ImageCrosshair:ImageCrosshair',  
              'ImageProcessor = imageProcessor.ImageProcessor:ImageProcessor',
              'ImagePicker = imageProcessor.ImagePicker:ImagePicker',
              'ImageThumbnail = imageProcessor.ImageThumbnail:ImageThumbnail',
              'TwoPeakFinder = imageProcessor.TwoPeakFinder:TwoPeakFinder',
          ],
          'karabo.middlelayer_device': [
              'ImageToSpectrum = imageProcessor.ImageToSpectrum:ImageToSpectrum',
              'ImageNormRoi = imageProcessor.ImageNormRoi:ImageNormRoi',
              'BeamShapeCoarse = imageProcessor.BeamShapeCoarse:BeamShapeCoarse',
          ],
      },
      package_data={},
      requires=[],
      )



# copy to subpaths with Karabo class files

shutil.copy(join(ROOT_FOLDER, '_version.py'),
            join(ROOT_FOLDER, "src/imageProcessor"))
