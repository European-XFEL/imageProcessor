#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on June 5, 2018
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################

from karabo.bound import (
    BOOL_ELEMENT, KARABO_CLASSINFO, VECTOR_INT32_ELEMENT, ImageData)

from ._version import version as deviceVersion
from .common import ImageProcOutputInterface
from .ImageProcessorBase import ImageProcessorBase


@KARABO_CLASSINFO("ImageApplyRoi", deviceVersion)
class ImageApplyRoi(ImageProcessorBase, ImageProcOutputInterface):

    @staticmethod
    def expectedParameters(expected):
        (
            BOOL_ELEMENT(expected).key("disable")
            .displayedName("Disable ROI")
            .description("No ROI will be applied, if set to True.")
            .assignmentOptional().defaultValue(False)
            .init()
            .commit(),

            VECTOR_INT32_ELEMENT(expected).key("roi")
            .displayedName("ROI")
            .description("The user-defined region of interest (ROI), "
                         "specified as [lowX, highX, lowY, highY].")
            .assignmentOptional().defaultValue([0, 10000, 0, 10000])
            .minSize(4).maxSize(4)
            .reconfigurable()
            .commit(),
        )

    def __init__(self, configuration):
        # always call superclass constructor first!
        super().__init__(configuration)

        self.registerInitialFunction(self.initialization)

    def initialization(self):
        """ This method will be called after the constructor. """
        roi = self["roi"]
        valid = self.valid_roi(roi)
        if not valid:
            self['disable'] = True
            self.logger.error("Initial ROI is invalid -> disabled")

    def preReconfigure(self, incomingReconfiguration):
        # always call ImageProcessorBase preReconfigure first!
        super().preReconfigure(incomingReconfiguration)

        if incomingReconfiguration.has('roi'):
            roi = incomingReconfiguration['roi']
            valid = self.valid_roi(roi)
            if valid:
                self['disable'] = False
                self.logger.info(f"Applying new roi {roi}")
            else:
                incomingReconfiguration.erase("roi")
                self.logger.error("New ROI is invalid -> rejected")

    # Overrides ImageProcessorBase.process_image
    def process_image(self, image_data, ts):
        if self['disable']:
            self.logger.debug("ROI disabled!")
            return image_data

        low_x, high_x, low_y, high_y = self['roi']

        data = image_data.getData()  # np.ndarray
        roi_offsets = list(image_data.getROIOffsets())  # input image offset

        if data.ndim == 2:
            # GRAY image
            cropped_image = ImageData(data[low_y:high_y, low_x:high_x])
            # Output image offsets
            roi_offsets[0] += low_y
            roi_offsets[1] += low_x

        elif data.ndim == 3 and (data.shape[2] in (2, 3, 4)):
            # YUV, RGB, RGBA and similar formats
            cropped_image = ImageData(data[low_y:high_y, low_x:high_x, :])
            # Output image offsets
            roi_offsets[0] += low_y
            roi_offsets[1] += low_x

        elif data.ndim == 3:
            # Stack of GRAY images
            cropped_image = ImageData(data[:, low_y:high_y, low_x:high_x])
            # Output image offsets
            roi_offsets[1] += low_y
            roi_offsets[2] += low_x

        else:
            raise RuntimeError(
                "Cannot apply ROI due to unrecognized image shape: "
                f"{data.shape}")

        cropped_image.setROIOffsets(roi_offsets)
        return cropped_image

    @staticmethod
    def valid_roi(roi):
        if roi[0] < 0 or roi[1] < roi[0]:
            return False
        if roi[2] < 0 or roi[3] < roi[2]:
            return False

        return True
