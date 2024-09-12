#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on November 26, 2015
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################

import copy
from threading import Lock

import numpy as np

from karabo.bound import (
    KARABO_CLASSINFO, OVERWRITE_ELEMENT, SLOT_ELEMENT, UINT32_ELEMENT, Dims,
    ImageData, State, Timestamp, Unit)

from ._version import version as deviceVersion
from .ImageProcessorBase import ImageProcessorBase


@KARABO_CLASSINFO("ImageBackgroundSubtractionBase", deviceVersion)
class ImageBackgroundSubtractionBase(ImageProcessorBase):

    @staticmethod
    def expectedParameters(expected):
        (
            OVERWRITE_ELEMENT(expected).key('state')
            .setNewOptions(
                State.ON, State.PROCESSING, State.ACQUIRING, State.ERROR)
            .commit(),

            SLOT_ELEMENT(expected).key('resetBackgroundImage')
            .displayedName("Reset Background Image")
            .description("Reset background image.")
            .commit(),

            SLOT_ELEMENT(expected).key('useAsBackgroundImage')
            .displayedName("Current Image(s) as Background")
            .description("Use the average of 'nImages' for the background "
                         "subtraction.")
            .allowedStates(State.ON, State.PROCESSING)
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
        self.KARABO_SLOT(self.useAsBackgroundImage)

    def preReconfigure(self, incomingReconfiguration):
        # always call parent's preReconfigure first!
        super().preReconfigure(incomingReconfiguration)

        if 'nImages' in incomingReconfiguration:
            self.reset_background()

    def reset_background(self, recalculate=True):
        with self.avg_lock:
            self.update_avg = recalculate  # Recalculate average
            self.n_images = 0
            self.avg_bkg_image = None
            self.bkg_image = None

    def calculate_background(self, img):
        with self.avg_lock:
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
                self.avg_bkg_image = self.avg_bkg_image / n_images
                self.bkg_image = self.avg_bkg_image.astype(img.dtype)
            else:
                self.log.DEBUG("Calculating background...")

    ##############################################
    #   Implementation of Callbacks              #
    ##############################################

    def onData(self, data, metaData):
        first_image = False
        if self['state'] == State.ON:
            self.log.INFO("Start of Stream")
            if self.update_avg:
                # Calculating background average
                self.updateState(State.ACQUIRING)
                self["status"] = "Acquiring background images"
            else:
                self.updateState(State.PROCESSING)
            first_image = True
        elif self['state'] == State.PROCESSING and self.update_avg:
            # Calculating background average
            self.updateState(State.ACQUIRING)
            self["status"] = "Acquiring background images"
        elif self['state'] == State.ACQUIRING and not self.update_avg:
            # Background average is now available
            self.updateState(State.PROCESSING)

        try:
            image_path = self['imagePath']
            if data.has(image_path):
                image_data = data[image_path]
            else:
                raise RuntimeError("data does not contain any image")

            if isinstance(image_data, list):
                # Convert to ImageData
                data = np.asarray(image_data)
                dims = Dims(len(image_data))
                image_data = ImageData(data, dims)
            elif isinstance(image_data, np.ndarray):
                # Convert to ImageData
                dims = Dims(*image_data.shape)
                image_data = ImageData(image_data, dims)

        except Exception as e:
            msg = f"Exception caught in onData: {e}"
            self.update_count(error=True, status=msg)
            return

        ts = Timestamp.fromHashAttributes(
            metaData.getAttributes('timestamp'))

        self.process_image(image_data, ts, first_image)

    def onEndOfStream(self, inputChannel):
        self.log.INFO("onEndOfStream called")
        self['inFrameRate'] = 0.
        self.updateState(State.ON)
        self['status'] = 'Idle'

    def process_image(self, image_data, ts, first_image):
        raise NotImplementedError(
            "This function must be overridden in the derived class.")

    ##############################################
    #   Implementation of Slots                  #
    ##############################################

    def resetBackgroundImage(self):
        self.log.INFO("Reset background image")
        self.reset_background(recalculate=False)

    def useAsBackgroundImage(self):
        self.log.INFO("Use current image(s) as background")
        self.reset_background()
