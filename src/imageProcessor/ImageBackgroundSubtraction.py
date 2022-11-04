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

            BOOL_ELEMENT(expected).key('convertToFloat')
            .displayedName('Convert to Float')
            .description('Use floating point pixel values for the '
                         'averaged image instead of the source type')
            .assignmentOptional().defaultValue(False)
            .expertAccess()
            .reconfigurable()
            .allowedStates(State.ON)
            .commit(),
        )

    def __init__(self, configuration):
        # always call superclass constructor first!
        super().__init__(configuration)

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

        self.process_image(image_data, ts, first_image)

    def onEndOfStream(self, inputChannel):
        self.log.INFO("onEndOfStream called")
        self['inFrameRate'] = 0.
        # Signals end of stream
        self.signalEndOfStreams()
        self.updateState(State.ON)
        self['status'] = 'Idle'

    def process_image(self, image_data, ts, first_image):
        self.refresh_frame_rate_in()

        try:
            self.current_image = image_data.getData()  # np.ndarray
            # Copy current image, before doing any processing
            # Also, convert it to float in order to avoid over- and underflows
            img = self.current_image.astype(np.float32)
            in_dtype = self.current_image.dtype
            if self['convertToFloat']:
                out_dtype = np.dtype('float32')
            else:
                out_dtype = in_dtype

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
                    if in_dtype == out_dtype:
                        img = self.current_image
                    elif img.dtype == out_dtype:
                        pass
                    else:
                        img = self.current_image.astype(out_dtype)
                    image_data.setData(img)
                    self.write_image(image_data, ts, first_image)
                    self.log.DEBUG("Original image copied to output channel")
                    return

                if self.bkg_image is None:
                    msg = (
                        "No bkg is loaded: original image copied to output "
                        "channel")
                    if self['status'] != msg:
                        self['status'] = msg
                        self.log.WARN(msg)

                    if in_dtype == out_dtype:
                        img = self.current_image
                    elif img.dtype == out_dtype:
                        pass
                    else:
                        img = self.current_image.astype(out_dtype)
                    image_data.setData(img)
                    self.write_image(image_data, ts, first_image)

                    return

                if self.bkg_image.shape == img.shape:
                    if out_dtype.kind in ('i', 'u'):  # integer type
                        max_value = np.iinfo(out_dtype).max
                        min_value = np.iinfo(out_dtype).min
                    elif out_dtype.kind == 'f':  # floating point
                        max_value = np.finfo(out_dtype).max
                        min_value = None
                    else:
                        max_value = None
                        min_value = None

                    # Add offset, subtract background, clip, and finally cast
                    # to the original dtype, or, if set by the users, to float
                    img = (img + self['offset'] - self.bkg_image).clip(
                        min=min_value, max=max_value)
                    if img.dtype != out_dtype:
                        img = img.astype(out_dtype)
                    self.log.DEBUG("Background image subtracted")

                    image_data.setData(img)
                    self.write_image(image_data, ts, first_image)
                    self.log.DEBUG("Image sent to output channel")

                    if self['status'] != "Processing":
                        self['status'] = "Processing"

                else:
                    msg = ("Cannot subtract background image... shapes are "
                           f"different: {self.bkg_image.shape} != {img.shape}")
                    self.update_count(error=True, msg=msg)

        except Exception as e:
            msg = f"Exception caught in process_image: {e}"
            self.update_count(error=True, msg=msg)

    def write_image(self, image, ts, first_image):
        """This function will: 1. update the device schema (if needed);
        2. write the image to the output channels; 3. refresh the error count
        and frame rates."""

        if first_image:
            # Update schema
            self.updateOutputSchema(image)

        self.writeImageToOutputs(image, ts)
        self.update_count()  # Success
        self.refresh_frame_rate_out()

    ##############################################
    #   Implementation of Slots                  #
    ##############################################

    def resetBackgroundImage(self):
        self.log.INFO("Reset background image")
        self.reset_background(recalculate=False)

    def save(self):
        self.log.DEBUG("Save background image to file")

        with self.avg_lock:
            try:
                if self.bkg_image is None:
                    raise RuntimeError("no bkg to be saved!")

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
                msg = f"Exception in save: {e}"
                self['status'] = msg
                if self['state'] != State.ERROR:
                    self.updateState(State.ERROR)
                raise

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
            msg = f"Exception in load: {e}"
            self['status'] = msg
            if self['state'] != State.ERROR:
                self.updateState(State.ERROR)
            raise

    def useAsBackgroundImage(self):
        self.log.INFO("Use current image(s) as background")
        self.reset_background()
