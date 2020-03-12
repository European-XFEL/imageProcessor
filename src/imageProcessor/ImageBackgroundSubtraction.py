#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on November 26, 2015
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

import numpy as np
import os.path
from PIL import Image

from karabo.bound import (
    BOOL_ELEMENT, ImageData, KARABO_CLASSINFO, PATH_ELEMENT,
    SLOT_ELEMENT, State, Timestamp
)

from image_processing.image_processing import imageSubtractBackground

try:
    from .common import ImageProcOutputInterface
    from .ImageProcessorBase import ImageProcessorBase
except ImportError:
    from imageProcessor.common import ImageProcOutputInterface
    from imageProcessor.ImageProcessorBase import ImageProcessorBase


@KARABO_CLASSINFO("ImageBackgroundSubtraction", "2.6")
class ImageBackgroundSubtraction(ImageProcessorBase, ImageProcOutputInterface):

    @staticmethod
    def expectedParameters(expected):
        (
            BOOL_ELEMENT(expected).key('disable')
            .displayedName("Disable")
            .description("Disable background subtraction.")
            .assignmentOptional().defaultValue(False)
            .reconfigurable()
            .commit(),

            PATH_ELEMENT(expected).key('imageFilename')
            .displayedName("Image Filename")
            .description("The full filename to the background image. "
                         "File format must be 'npy', 'raw' or TIFF.")
            .assignmentOptional().defaultValue("background.npy")
            .reconfigurable()
            .commit(),

            SLOT_ELEMENT(expected).key('resetBackgroundImage')
            .displayedName("Reset Background Image")
            .description("Reset background image.")
            .commit(),

            SLOT_ELEMENT(expected).key('save')
            .displayedName("Save Background Image")
            .description("Save to file the current image.")
            .commit(),

            SLOT_ELEMENT(expected).key('load')
            .displayedName("Load Background Image")
            .description("Load a background image from file.")
            .commit(),

            SLOT_ELEMENT(expected).key('useAsBackgroundImage')
            .displayedName("Current Image as Background")
            .description("Use the current image as background image.")
            .commit(),

        )

    def __init__(self, configuration):
        # always call superclass constructor first!
        super(ImageBackgroundSubtraction, self).__init__(configuration)

        # Current image
        self.current_image = None

        # Background image
        self.bkg_image = None

        # Register call-backs
        self.KARABO_ON_DATA("input", self.onData)
        self.KARABO_ON_EOS("input", self.onEndOfStream)

        # Register additional slots
        self.KARABO_SLOT(self.resetBackgroundImage)
        self.KARABO_SLOT(self.save)
        self.KARABO_SLOT(self.load)
        self.KARABO_SLOT(self.useAsBackgroundImage)

    ##############################################
    #   Implementation of Callbacks              #
    ##############################################

    def onData(self, data, metaData):
        first_image = False
        if self['state'] == State.ON:
            self.log.INFO("Start of Stream")
            self.updateState(State.PROCESSING)
            first_image = True

        try:
            if data.has('data.image'):
                image_data = data['data.image']
            elif data.has('image'):
                # To ensure backward compatibility
                # with older versions of cameras
                image_data = data['image']
            else:
                raise RuntimeError("data does not contain any image")
        except Exception as e:
            msg = "Exception caught in onData: {}".format(e)
            self.update_count(error=True, msg=msg)
            return

        ts = Timestamp.fromHashAttributes(
            metaData.getAttributes('timestamp'))

        if first_image:
            self.updateOutputSchema(image_data)

        self.process_image(image_data, ts)

    def onEndOfStream(self, inputChannel):
        self.log.INFO("onEndOfStream called")
        self['inFrameRate'] = 0.
        # Signals end of stream
        self.signalEndOfStreams()
        self.updateState(State.ON)
        self['status'] = 'ON'

    def process_image(self, image_data, ts):
        self.refresh_frame_rate_in()

        try:
            self.current_image = image_data.getData()  # np.ndarray
            # Copy current image, before doing any processing
            # Also, convert it to float in order to allow negative values
            img = self.current_image.astype('float')
            bpp = image_data.getBitsPerPixel()
            encoding = image_data.getEncoding()

            disable = self['disable']
            if disable:
                self.log.DEBUG("Background subtraction disabled!")
                self.writeImageToOutputs(image_data, ts)
                self.log.DEBUG("Original image copied to output channel")
                return

            if self.bkg_image is None:
                self.log.DEBUG("No background image loaded!")
                self.writeImageToOutputs(image_data, ts)
                self.log.DEBUG("Original image copied to output channel")
                return

            if self.bkg_image.shape == img.shape:
                # Subtract background image
                imageSubtractBackground(img, self.bkg_image)

                self.log.DEBUG("Background image subtracted")

                image_data = ImageData(img, bitsPerPixel=bpp,
                                       encoding=encoding)
                self.writeImageToOutputs(image_data, ts)
                self.log.DEBUG("Image sent to output channel")
                self.update_count()  # Success

            else:
                msg = ("Cannot subtract background image... shapes are "
                       "different: {} != {}"
                       .format(self.bkg_image.shape, img.shape))
                self.update_count(error=True, msg=msg)

        except Exception as e:
            msg = "Exception caught in process_image: {}".format(e)
            self.update_count(error=True, msg=msg)

    ##############################################
    #   Implementation of Slots                  #
    ##############################################

    def resetBackgroundImage(self):
        self.log.INFO("Reset background image")
        self.bkg_image = None

    def save(self):
        self.log.INFO("Save background image to file")

        if self.bkg_image is None:
            self.log.WARN("No background image loaded!")
            return

        try:
            # Try to save image file
            filename = self['imageFilename']
            extension = os.path.splitext(filename)[1]

            if extension in ('.npy', '.NPY'):
                self.bkg_image.dump(filename)
                self.log.INFO('Background image saved to file ' + filename)

            elif extension in ('.raw', ".RAW"):
                self.bkg_image.tofile(filename)
                self.log.INFO('Background image saved to file ' + filename)

            elif extension in ('.tif', '.tiff', '.TIF', '.TIFF'):
                if self.bkg_image.dtype == 'uint8':
                    pilImage = Image.fromarray(self.bkg_image)
                    pilImage.save(filename)
                    self.log.INFO('Background image saved to file ' + filename)
                else:
                    raise RuntimeError("dtype must be uint8 but is {}"
                                       .format(self.bkg_image.dtype))
            else:
                raise RuntimeError("unsupported file type {}"
                                   .format(filename))

        except Exception as e:
            self.log.ERROR("Exception caught in save: {}".format(e))
            if self['state'] != State.ERROR:
                self.updateState(State.ERROR)

    def load(self):
        self.log.DEBUG("Load background image from file")

        try:
            # Try to load image file
            filename = self['imageFilename']
            extension = os.path.splitext(filename)[1]

            if extension in ('.npy', '.NPY'):
                data = np.load(filename)
                self.log.INFO("Background image loaded from file {}"
                              .format(filename))
                self.bkg_image = data

            elif extension in ('.raw', ".RAW"):
                if self.current_image is None:
                    raise RuntimeError("cannot load background image from "
                                       "'raw' file: no current image "
                                       "available to get pixelFormat and "
                                       "image shape from")

                else:
                    shape = self.current_image.shape
                    d_type = self.current_image.dtype
                    data = np.fromfile(filename, dtype=d_type).reshape(shape)
                    self.log.INFO("Background image loaded from file {}"
                                  .format(filename))
                    self.bkg_image = data

            elif extension in ('.tif', '.tiff', '.TIF', '.TIFF'):
                pil_image = Image.open(filename)
                data = np.array(pil_image)
                self.log.INFO("Background image loaded from file {}"
                              .format(filename))
                self.bkg_image = data

            else:
                raise RuntimeError("unsupported file type {}"
                                   .format(filename))

        except Exception as e:
            self.log.ERROR("Exception caught in load: {}".format(e))
            if self['state'] != State.ERROR:
                self.updateState(State.ERROR)

    def useAsBackgroundImage(self):
        self.log.DEBUG("Use current image as background")
        if self.current_image is not None:
            # Copy current image to background image
            self.bkg_image = np.copy(self.current_image)
            self.log.INFO("Current image loaded as background")
        else:
            self.log.WARN("No current image available to be used as "
                          "background")
            if self['state'] != State.ERROR:
                self.updateState(State.ERROR)
