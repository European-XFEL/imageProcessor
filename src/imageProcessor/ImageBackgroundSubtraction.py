#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on November 26, 2015
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

import copy
import os.path
import numpy as np

from PIL import Image
from threading import Lock

from karabo.bound import (
    BOOL_ELEMENT, KARABO_CLASSINFO, SLOT_ELEMENT, State, STRING_ELEMENT,
    Timestamp, UINT32_ELEMENT, Unit
)

try:
    from .common import ImageProcOutputInterface
    from .ImageProcessorBase import ImageProcessorBase
    from ._version import version as deviceVersion
except ImportError:
    from imageProcessor.common import ImageProcOutputInterface
    from imageProcessor.ImageProcessorBase import ImageProcessorBase
    from imageProcessor._version import version as deviceVersion


@KARABO_CLASSINFO("ImageBackgroundSubtraction", deviceVersion)
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

            STRING_ELEMENT(expected).key('imageFilename')
            .displayedName("Image Filename")
            .description("The full filename to the background image. "
                         "File format must be 'npy', 'raw' or TIFF.")
            .assignmentOptional().noDefaultValue()
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
            .displayedName("Current Image(s) as Background")
            .description("Use the average of 'nImages' for the background "
                         "subtraction.")
            .commit(),

            UINT32_ELEMENT(expected).key('offset')
            .displayedName("Offset")
            .description("The offset to be added to the input image, before "
                         "doing the background subtraction.")
            .assignmentOptional().defaultValue(100)
            .reconfigurable()
            .commit(),

            UINT32_ELEMENT(expected).key('nImages')
            .displayedName('Number of Background Images')
            .description('Number of background images to be averaged.')
            .unit(Unit.NUMBER)
            .assignmentOptional().defaultValue(10)
            .minInc(1).maxInc(100)
            .reconfigurable()
            .commit(),
        )

    def __init__(self, configuration):
        # always call superclass constructor first!
        super(ImageBackgroundSubtraction, self).__init__(configuration)

        # Current image
        self.current_image = None

        # Background image
        self.bkg_image = None

        self.avg_bkg_image = None  # Background average
        self.n_images = 0
        self.update_avg = False  # Average needs update
        self.avg_lock = Lock()  # Lock for bkg image and avg

        # Register call-backs
        self.KARABO_ON_DATA("input", self.onData)
        self.KARABO_ON_EOS("input", self.onEndOfStream)

        # Register additional slots
        self.KARABO_SLOT(self.resetBackgroundImage)
        self.KARABO_SLOT(self.save)
        self.KARABO_SLOT(self.load)
        self.KARABO_SLOT(self.useAsBackgroundImage)

        if 'imageFilename' not in configuration:
            device_id = self['deviceId']
            fname = device_id.replace('/', '_')
            fname = f'{fname}.npy'
            configuration['imageFilename'] = fname

    def preReconfigure(self, incomingReconfiguration):
        if 'nImages' in incomingReconfiguration:
            self.reset_background()

    def reset_background(self, recalculate=True):
        with self.avg_lock:
            self.update_avg = recalculate  # Recalculate average
            self.n_images = 0
            self.avg_bkg_image = None
            self.bkg_image = None

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
            # Also, convert it to float in order to avoid over- and underflows
            img = self.current_image.astype(np.float32)
            d_type = self.current_image.dtype

            with self.avg_lock:
                if self.update_avg:
                    # Calculate background image average
                    n_images = self['nImages']
                    if self.n_images == 0:
                        self.avg_bkg_image = copy.deepcopy(img)
                        self.n_images = 1
                    elif self.n_images < n_images:
                        self.avg_bkg_image += img
                        self.n_images += 1

                    if self.n_images == n_images:
                        self.update_avg = False
                        self.avg_bkg_image /= n_images
                        self.bkg_image = self.avg_bkg_image
                    else:
                        self.log.DEBUG("Calculating background...")
                        return

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
                    if d_type.kind in ('i', 'u'):  # integer type
                        max_value = np.iinfo(d_type).max
                    elif d_type.kind == 'f':  # floating point
                        max_value = np.finfo(d_type).max
                    else:
                        max_value = None

                    # Add offset, subtract background, clip, and finally cast
                    # to the original dtype
                    img = (img + self['offset'] - self.bkg_image).clip(
                        min=0, max=max_value).astype(d_type)

                    self.log.DEBUG("Background image subtracted")

                    image_data.setData(img)
                    self.writeImageToOutputs(image_data, ts)
                    self.log.DEBUG("Image sent to output channel")
                    self.update_count()  # Success

                else:
                    msg = ("Cannot subtract background image... shapes are "
                           f"different: {self.bkg_image.shape} != {img.shape}")
                    self.update_count(error=True, msg=msg)

        except Exception as e:
            msg = f"Exception caught in process_image: {e}"
            self.update_count(error=True, msg=msg)

    ##############################################
    #   Implementation of Slots                  #
    ##############################################

    def resetBackgroundImage(self):
        self.log.INFO("Reset background image")
        self.reset_background(recalculate=False)

    def save(self):
        self.log.INFO("Save background image to file")

        with self.avg_lock:
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
                        self.log.INFO(
                            'Background image saved to file ' + filename)
                    else:
                        raise RuntimeError("dtype must be uint8 but is "
                                           f"{self.bkg_image.dtype}")
                else:
                    raise RuntimeError(f"unsupported file type {filename}")

            except Exception as e:
                self.log.ERROR(f"Exception caught in save: {e}")
                if self['state'] != State.ERROR:
                    self.updateState(State.ERROR)

    def load(self):
        self.log.DEBUG("Load background image from file")

        try:
            # Try to load image file
            filename = self['imageFilename']
            extension = os.path.splitext(filename)[1]

            if extension in ('.npy', '.NPY'):
                data = np.load(filename, allow_pickle=True)
                self.log.INFO(f"Background image loaded from file {filename}")
                with self.avg_lock:
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
                    self.log.INFO(
                        f"Background image loaded from file {filename}")
                    with self.avg_lock:
                        self.bkg_image = data

            elif extension in ('.tif', '.tiff', '.TIF', '.TIFF'):
                pil_image = Image.open(filename)
                data = np.array(pil_image)
                self.log.INFO(f"Background image loaded from file {filename}")
                with self.avg_lock:
                    self.bkg_image = data

            else:
                raise RuntimeError(f"unsupported file type {filename}")

        except Exception as e:
            self.log.ERROR(f"Exception caught in load: {e}")
            if self['state'] != State.ERROR:
                self.updateState(State.ERROR)

    def useAsBackgroundImage(self):
        self.log.INFO("Use current image(s) as background")
        self.reset_background()
