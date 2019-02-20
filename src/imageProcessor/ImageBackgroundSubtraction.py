#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on November 26, 2015
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

import numpy as np
import os.path
from PIL import Image

from karabo.bound import (
    BOOL_ELEMENT, DOUBLE_ELEMENT, ImageData, IMAGEDATA_ELEMENT,
    INPUT_CHANNEL, KARABO_CLASSINFO, NODE_ELEMENT, OVERWRITE_ELEMENT,
    PATH_ELEMENT, PythonDevice, Schema, SLOT_ELEMENT, State, Timestamp,
    UINT32_ELEMENT, Unit
)

from image_processing.image_processing import imageSubtractBackground
from processing_utils.rate_calculator import RateCalculator

from .common import ImageProcOutputInterface


@KARABO_CLASSINFO("ImageBackgroundSubtraction", "2.3")
class ImageBackgroundSubtraction(PythonDevice, ImageProcOutputInterface):

    @staticmethod
    def expectedParameters(expected):
        data = Schema()
        (
            OVERWRITE_ELEMENT(expected).key('state')
            .setNewOptions(State.ON, State.PROCESSING, State.ERROR)
            .setNewDefaultValue(State.ON)
            .commit(),

            NODE_ELEMENT(data).key('data')
            .displayedName("Data")
            .commit(),

            IMAGEDATA_ELEMENT(data).key('data.image')
            .commit(),

            INPUT_CHANNEL(expected).key('input')
            .displayedName("Input")
            .dataSchema(data)
            .commit(),

            # Images should be dropped if processor is too slow
            OVERWRITE_ELEMENT(expected).key('input.onSlowness')
            .setNewDefaultValue("drop")
            .commit(),

            DOUBLE_ELEMENT(expected).key('frameRate')
            .displayedName("Frame Rate")
            .description("The actual frame rate.")
            .unit(Unit.HERTZ)
            .readOnly()
            .commit(),

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

            UINT32_ELEMENT(expected).key('errorCount')
            .displayedName("Error Count")
            .description("Number of errors.")
            .unit(Unit.COUNT)
            .readOnly().initialValue(0)
            .commit(),

            SLOT_ELEMENT(expected).key('reset')
            .displayedName('Reset')
            .description("Reset error count.")
            .commit(),
        )

    def __init__(self, configuration):
        # always call PythonDevice constructor first!
        super(ImageBackgroundSubtraction, self).__init__(configuration)

        # Current image
        self.current_image = None

        # Background image
        self.bkg_image = None

        # Variables for frames per second computation
        self.frame_rate = RateCalculator(refresh_interval=1.0)

        # Register call-backs
        self.KARABO_ON_DATA("input", self.onData)
        self.KARABO_ON_EOS("input", self.onEndOfStream)

        # Register additional slots
        self.registerSlot(self.resetBackgroundImage)
        self.registerSlot(self.save)
        self.registerSlot(self.load)
        self.registerSlot(self.useAsBackgroundImage)
        self.KARABO_SLOT(self.reset)

        self.MAX_ERROR_COUNT = 5  # TODO make it reconfigurable?

    ##############################################
    #   Implementation of Callbacks              #
    ##############################################

    def onData(self, data, metaData):
        first_image = False
        if self['state'] == State.ERROR:
            return
        elif self['state'] == State.ON:
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
            error_count = self['errorCount']
            self['errorCount'] = error_count + 1
            if error_count < self.MAX_ERROR_COUNT:
                self.log.ERROR("Exception caught in onData: {}".format(e))
            elif self['state'] != State.ERROR:
                self.updateState(State.ERROR)
            return

        ts = Timestamp.fromHashAttributes(
            metaData.getAttributes('timestamp'))

        if first_image:
            self.updateOutputSchema(image_data)

        self.process_image(image_data, ts)

    def onEndOfStream(self):
        self.log.INFO("onEndOfStream called")
        self['frameRate'] = 0.
        self['errorCount'] = 0
        # Signals end of stream
        self.signalEndOfStreams()
        self.updateState(State.ON)

    def process_image(self, image_data, ts):
        self.refresh_frame_rate()

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

            else:
                error_count = self['errorCount']
                self['errorCount'] = error_count + 1
                if error_count < self.MAX_ERROR_COUNT:
                    self.log.WARN("Cannot subtract background image... "
                                  "shapes are different: {} != {}"
                                  .format(self.bkg_image.shape, img.shape))

        except Exception as e:
            error_count = self['errorCount']
            self['errorCount'] = error_count + 1
            if error_count < self.MAX_ERROR_COUNT:
                self.log.ERROR("Exception caught in processImage: {}"
                               .format(e))
            elif self['state'] != State.ERROR:
                self.updateState(State.ERROR)

    def refresh_frame_rate(self):
        self.frame_rate.update()
        fps = self.frame_rate.refresh()
        if fps:
            self['frameRate'] = fps
            self.log.DEBUG("Input rate {} Hz".format(fps))

    ##############################################
    #   Implementation of Slots                  #
    ##############################################

    def reset(self):
        self.log.INFO("Reset error counter")
        self['errorCount'] = 0
        self.updateState(State.ON)

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
