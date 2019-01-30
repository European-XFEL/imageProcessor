#!/usr/bin/env python

#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on November 27, 2015
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

import numpy as np
import os.path
from PIL import Image

from karabo.bound import (
    BOOL_ELEMENT, DOUBLE_ELEMENT, Hash, ImageData, IMAGEDATA_ELEMENT,
    INPUT_CHANNEL, KARABO_CLASSINFO, NODE_ELEMENT, OUTPUT_CHANNEL,
    OVERWRITE_ELEMENT, PATH_ELEMENT, PythonDevice, Schema, SLOT_ELEMENT,
    State, STRING_ELEMENT, Timestamp, Unit, VECTOR_INT32_ELEMENT,
    VECTOR_STRING_ELEMENT
)

from image_processing.image_processing import (
    imageApplyMask, imageSelectRegion
)

from processing_utils.rate_calculator import RateCalculator


@KARABO_CLASSINFO("ImageApplyMask", "2.2")
class ImageApplyMask(PythonDevice):

    def __init__(self, configuration):
        # always call PythonDevice constructor first!
        super(ImageApplyMask, self).__init__(configuration)

        # Current image
        self.currentImage = None

        # Mask
        self.mask = None

        # Register additional slots
        self._ss.registerSlot(self.resetMask)
        self._ss.registerSlot(self.loadMask)

        # Register call-backs
        self.KARABO_ON_DATA("input", self.onData)
        self.KARABO_ON_EOS("input", self.onEndOfStream)

        self.registerInitialFunction(self.initialization)

        # Variables for frames per second computation
        self.frame_rate = RateCalculator(refresh_interval=1.0)

    @staticmethod
    def expectedParameters(expected):
        data = Schema()
        (
            OVERWRITE_ELEMENT(expected).key("state")
                .setNewOptions(State.PASSIVE, State.ACTIVE)
                .setNewDefaultValue(State.PASSIVE)
                .commit(),

            VECTOR_STRING_ELEMENT(expected).key("interfaces")
                .displayedName("Interfaces")
                .readOnly()
                .initialValue(["Processor"])
                .commit(),

            NODE_ELEMENT(data).key("data")
                .displayedName("Data")
                .commit(),

            IMAGEDATA_ELEMENT(data).key("data.image")
                .displayedName("Image")
                .commit(),

            INPUT_CHANNEL(expected).key("input")
                .displayedName("Input")
                .dataSchema(data)
                .commit(),

            # Images should be dropped if processor is too slow
            OVERWRITE_ELEMENT(expected).key("input.onSlowness")
                .setNewDefaultValue("drop")
                .commit(),

            OUTPUT_CHANNEL(expected).key("output")
                .displayedName("Output")
                .dataSchema(data)
                .commit(),

            DOUBLE_ELEMENT(expected).key("frameRate")
                .displayedName("Frame Rate")
                .description("The actual frame rate.")
                .unit(Unit.HERTZ)
                .readOnly()
                .commit(),

            BOOL_ELEMENT(expected).key("disable")
                .displayedName("Disable Mask")
                .description("No mask will be applied, if set to True.")
                .assignmentOptional().defaultValue(False)
                .reconfigurable()
                .commit(),

            STRING_ELEMENT(expected).key("maskType")
                .displayedName("Mask Type")
                .description("The mask type: rectangular or arbitrary (loaded "
                             "from file).")
                .options("rectangular,fromFile")
                .assignmentOptional().defaultValue("fromFile")
                .reconfigurable()
                .commit(),

            VECTOR_INT32_ELEMENT(expected).key("x1x2y1y2")
                .displayedName("Rectangular Selected Region")
                .description("The rectangular selected region: "
                             "x1, x2, y1, y2.")
                .assignmentOptional().defaultValue([0, 10000, 0, 10000])
                .minSize(4).maxSize(4)
                .unit(Unit.PIXEL)
                .reconfigurable()
                .commit(),

            PATH_ELEMENT(expected).key("maskFilename")
                .displayedName("Mask Filename")
                .description("The full path to the mask file. File format "
                             "must be 'npy', 'raw' or TIFF. "
                             "Pixel value will be set to 0, where mask is <=0.")
                .assignmentOptional().defaultValue("mask.npy")
                .reconfigurable()
                .commit(),

            SLOT_ELEMENT(expected).key("resetMask")
                .displayedName("Reset Mask")
                .description("Discard the loaded mask.")
                .commit(),

            SLOT_ELEMENT(expected).key("loadMask")
                .displayedName("Load Mask")
                .description("Load the mask from a file.")
                .commit(),
        )

    def initialization(self):
        """ This method will be called after the constructor. """

    ##############################################
    #   Implementation of Callbacks              #
    ##############################################

    def onData(self, data, metaData):
        if self.get("state") == State.PASSIVE:
            self.log.INFO("Start of Stream")
            self.updateState(State.ACTIVE)

        try:
            if data.has('data.image'):
                imageData = data['data.image']
            elif data.has('image'):
                # To ensure backward compatibility
                # with older versions of cameras
                imageData = data['image']
            else:
                self.log.DEBUG("data does not have any image")
                return

            ts = Timestamp.fromHashAttributes(
                metaData.getAttributes('timestamp'))
            self.processImage(imageData, ts)  # Process image

        except Exception as e:
            self.log.ERROR("Exception caught in onData: %s" % str(e))

    def onEndOfStream(self, inputChannel):
        self.log.INFO("End of Stream")
        self.set("frameRate", 0.)
        # Signals end of stream
        self.signalEndOfStream("output")
        self.updateState(State.PASSIVE)

    ##############################################
    #   Implementation of processImage           #
    ##############################################

    def processImage(self, imageData, ts):
        self.refreshFrameRate()

        try:
            disable = self.get("disable")
            if disable:
                self.log.DEBUG("Mask disabled!")
                self.writeChannel("output", Hash("data.image", imageData), ts)
                self.log.DEBUG("Original image copied to output channel")
                return

            self.currentImage = imageData.getData()  # np.ndarray
            img = self.currentImage  # Shallow copy
            self.log.DEBUG("Image loaded")

            maskType = self.get("maskType")
            if maskType == "fromFile":
                if self.mask is None:
                    self.log.WARN("No mask loaded!")
                    self.writeChannel("output",
                                      Hash("data.image", ImageData(img)), ts)
                    self.log.DEBUG("Original image copied to output channel")
                    return

                else:
                    if self.mask.shape == img.shape:
                        img = imageApplyMask(img, self.mask, copy=True)

                        self.log.DEBUG("Mask applied")
                        self.writeChannel("output",
                                          Hash("data.image", ImageData(img)))
                        self.log.DEBUG("Image sent to output channel")
                        return

                    else:
                        self.log.WARN("Cannot apply mask... shapes are "
                                      "different: %s != %s"
                                      % (str(self.mask.shape), str(img.shape)))
                        return

            elif maskType == "rectangular":
                x1x2y1y2 = self.get("x1x2y1y2")
                if img.ndim == 2 or img.ndim == 3:
                    img = imageSelectRegion(img, *x1x2y1y2, copy=True)
                else:
                    self.log.WARN("Cannot apply rectangular region, "
                                  "image.ndim: %d", img.ndim)
                    return

                self.log.DEBUG("Rectangular region selected")
                self.writeChannel("output",
                                  Hash("data.image", ImageData(img)))
                self.log.DEBUG("Image sent to output channel")

            else:
                self.log.WARN("Unknown option for maskType: %s" % maskType)

        except Exception as e:
            self.log.ERROR("Exception caught in processImage: %s" % str(e))

    ##############################################
    #   Implementation of Slots                  #
    ##############################################

    def resetMask(self):
        self.log.INFO("Reset mask")
        self.mask = None
        self.set("maskType", "fromFile")

    def loadMask(self):
        self.log.INFO("Load mask")

        try:
            # Try to load image file
            filename = self.get("maskFilename")
            extension = os.path.splitext(filename)[1]

            if extension == '.npy':
                data = np.load(filename)
                self.log.INFO('Mask loaded from file ' + filename)
                self.mask = data

            elif extension in ('.raw', ".RAW"):
                if self.currentImage is None:
                    self.log.ERROR("Cannot load mask from 'raw' file: "
                                   "no current image available to get "
                                   "pixelFormat and image shape from")

                else:
                    shape = self.currentImage.shape
                    data = np.fromfile(filename, dtype=self.currentImage.dtype
                                       ).reshape(shape)
                    self.log.INFO('Mask loaded from file ' + filename)
                    self.mask = data

            elif extension in ('.tif', '.tiff', '.TIF', '.TIFF'):
                pilImage = Image.open(filename)
                data = np.array(pilImage)
                self.log.INFO('Mask loaded from file ' + filename)
                self.mask = data

            else:
                self.log.ERROR("Cannot load mask from %s: unsupported format"
                               % filename)

        except Exception as e:
            self.log.ERROR("Exception caught in loadMask: %s" % str(e))

    def refreshFrameRate(self):
        self.frame_rate.update()
        fps = self.frame_rate.refresh()
        if fps:
            self['frameRate'] = fps
            self.log.DEBUG('Input rate %f Hz' % fps)
