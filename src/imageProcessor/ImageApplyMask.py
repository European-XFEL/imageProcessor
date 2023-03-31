#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on November 27, 2015
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################

import os.path

import numpy as np
from PIL import Image

from karabo.bound import (
    BOOL_ELEMENT, ImageData, KARABO_CLASSINFO, PATH_ELEMENT, SLOT_ELEMENT,
    State, STRING_ELEMENT, Timestamp, Unit, VECTOR_INT32_ELEMENT
)

from image_processing.image_processing import imageApplyMask, imageSelectRegion

try:
    from .common import ImageProcOutputInterface
    from .ImageProcessorBase import ImageProcessorBase
    from ._version import version as deviceVersion
except ImportError:
    from imageProcessor.common import ImageProcOutputInterface
    from imageProcessor.ImageProcessorBase import ImageProcessorBase
    from imageProcessor._version import version as deviceVersion


@KARABO_CLASSINFO("ImageApplyMask", deviceVersion)
class ImageApplyMask(ImageProcessorBase, ImageProcOutputInterface):

    @staticmethod
    def expectedParameters(expected):
        (
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
                         "must be 'npy', 'raw' or TIFF. Pixel value "
                         "will be set to 0, where mask is <=0.")
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

    def __init__(self, configuration):
        # always call superclass constructor first!
        super().__init__(configuration)

        # Current image
        self.current_image = None

        # Mask
        self.mask_image = None

        # Register additional slots
        self.KARABO_SLOT(self.resetMask)
        self.KARABO_SLOT(self.loadMask)

        # Register call-backs
        self.KARABO_ON_DATA("input", self.onData)
        self.KARABO_ON_EOS("input", self.onEndOfStream)

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
            msg = f"Exception caught in onData: {e}"
            self.update_count(error=True, status=msg)
            return

        ts = Timestamp.fromHashAttributes(
            metaData.getAttributes('timestamp'))

        if first_image:
            self.updateOutputSchema(image_data)

        self.process_image(image_data, ts)  # Process image

    def onEndOfStream(self, inputChannel):
        self.log.INFO("onEndOfStream called")
        self['inFrameRate'] = 0.
        # Signals end of stream
        self.signalEndOfStreams()
        self.updateState(State.ON)
        self['status'] = 'Idle'

    def process_image(self, image_data, ts):
        self.refresh_frame_rate_in()

        try:
            disable = self['disable']
            if disable:
                self.log.DEBUG("Mask disabled!")
                self.writeImageToOutputs(image_data, ts)
                self.log.DEBUG("Original image copied to output channel")
                self.update_count()  # Success
                self.refresh_frame_rate_out()
                return

            self.current_image = image_data.getData()  # np.ndarray
            img = self.current_image  # Shallow copy
            self.log.DEBUG("Image loaded")

            mask_type = self['maskType']
            if mask_type == "fromFile":
                if self.mask_image is None:
                    raise RuntimeError("No mask loaded!")
                else:
                    if self.mask_image.shape == img.shape:
                        img = imageApplyMask(img, self.mask_image, copy=True)

                        self.log.DEBUG("Mask applied")
                        self.writeImageToOutputs(ImageData(img), ts)
                        self.log.DEBUG("Image sent to output channel")
                        self.update_count()  # Success
                        self.refresh_frame_rate_out()
                        return

                    else:
                        msg = ("Cannot apply mask... shapes are different: "
                               f"{self.bkg_image.shape} != {img.shape}")
                        raise RuntimeError(msg)

            elif mask_type == "rectangular":
                x1x2y1y2 = self['x1x2y1y2']
                if img.ndim == 2 or img.ndim == 3:
                    img = imageSelectRegion(img, *x1x2y1y2, copy=True)
                else:
                    msg = ("Cannot apply rectangular region, as "
                           f"image.ndim: {img.ndim}")
                    raise RuntimeError(msg)

                self.log.DEBUG("Rectangular region selected")
                self.writeImageToOutputs(ImageData(img), ts)
                self.log.DEBUG("Image sent to output channel")
                self.update_count()  # Success
                self.refresh_frame_rate_out()
                return

            else:
                msg = f"Unknown option for maskType: {mask_type}"
                raise RuntimeError(msg)

        except Exception as e:
            msg = f"Exception caught in process_image: {e}"
            self.update_count(error=True, status=msg)

    ##############################################
    #   Implementation of Slots                  #
    ##############################################

    def resetMask(self):
        self.log.INFO("Reset mask")
        self.mask_image = None
        self['maskType'] = 'fromFile'

    def loadMask(self):
        self.log.INFO("Load mask")

        try:
            # Try to load image file
            filename = self['maskFilename']
            extension = os.path.splitext(filename)[1]

            if extension == '.npy':
                data = np.load(filename)
                self.log.INFO('Mask loaded from file ' + filename)
                self.mask_image = data

            elif extension in ('.raw', ".RAW"):
                if self.current_image is None:
                    raise RuntimeError("Cannot load mask from 'raw' file: "
                                       "no current image available to get "
                                       "pixelFormat and image shape from")

                else:
                    shape = self.current_image.shape
                    data = np.fromfile(filename, dtype=self.current_image.dtype
                                       ).reshape(shape)
                    self.log.INFO('Mask loaded from file ' + filename)
                    self.mask_image = data

            elif extension in ('.tif', '.tiff', '.TIF', '.TIFF'):
                pil_image = Image.open(filename)
                data = np.array(pil_image)
                self.log.INFO(f"Mask loaded from file {filename}")
                self.mask_image = data

            else:
                raise RuntimeError(f"Cannot load mask from {filename}: "
                                   "unsupported image format")

        except Exception as e:
            self.log.ERROR(f"Exception caught in loadMask: {e}")
            if self['state'] != State.ERROR:
                self.updateState(State.ERROR)
