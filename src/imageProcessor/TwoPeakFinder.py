#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on November 14, 2018
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################
import numpy as np

from image_processing.image_processing import (
    imageSumAlongY, peakParametersEval)
from karabo.bound import (
    DOUBLE_ELEMENT, KARABO_CLASSINFO, UINT32_ELEMENT, VECTOR_UINT32_ELEMENT,
    Hash, ImageData, State, Unit)

from ._version import version as deviceVersion
from .ImageProcessorBase import ImageProcessorBase


def find_peaks(img_x, zero_point):
    """Find two peaks - one left one right - from zero_point"""
    value_1, pos_1, fwhm_1 = peakParametersEval(img_x[zero_point::-1])
    value_2, pos_2, fwhm_2 = peakParametersEval(img_x[zero_point:])
    pos_1 = zero_point - pos_1
    pos_2 += zero_point

    return value_1, pos_1, fwhm_1, value_2, pos_2, fwhm_2


@KARABO_CLASSINFO("TwoPeakFinder", deviceVersion)
class TwoPeakFinder(ImageProcessorBase):

    def __init__(self, configuration):
        # always call superclass constructor first!
        super().__init__(configuration)

        # Register call-backs
        self.KARABO_ON_EOS("input", self.onEndOfStream)

    @staticmethod
    def expectedParameters(expected):
        (
            UINT32_ELEMENT(expected).key('zeroPoint')
            .displayedName('Zero Point')
            .description("The device will try to find a peak left, and "
                         "a peak right, from this point.")
            .unit(Unit.PIXEL)
            .assignmentOptional().defaultValue(0)
            .reconfigurable()
            .commit(),

            UINT32_ELEMENT(expected).key('threshold')
            .displayedName('Threshold')
            .description("TODO - currently unused")
            .unit(Unit.NUMBER)
            .assignmentOptional().defaultValue(0)
            .reconfigurable()
            .commit(),

            VECTOR_UINT32_ELEMENT(expected).key('roi')
            .displayedName('Region-of-Interest')
            .description("The user-defined region of interest (ROI), "
                         "specified as [lowX, highX]. "
                         "[0, 0] will be interpreted as 'whole range'.")
            .unit(Unit.PIXEL)
            .assignmentOptional().defaultValue([0, 0])
            .reconfigurable()
            .commit(),

            DOUBLE_ELEMENT(expected).key('peak1Value')
            .displayedName("Peak 1 Value")
            .description("Amplitude of the 1st peak.")
            .unit(Unit.NUMBER)
            .readOnly()
            .commit(),

            UINT32_ELEMENT(expected).key('peak1Position')
            .displayedName("Peak 1 Position")
            .description("Position of the 1st peak.")
            .unit(Unit.PIXEL)
            .readOnly()
            .commit(),

            UINT32_ELEMENT(expected).key('peak1Fwhm')
            .displayedName("Peak 1 FWHM")
            .description("FWHM of the 1st peak.")
            .unit(Unit.PIXEL)
            .readOnly()
            .commit(),

            DOUBLE_ELEMENT(expected).key('peak2Value')
            .displayedName("Peak 2 Value")
            .description("Amplitude of the 2nd peak.")
            .unit(Unit.NUMBER)
            .readOnly()
            .commit(),

            UINT32_ELEMENT(expected).key('peak2Position')
            .displayedName("Peak 2 Position")
            .description("Position of the 2nd peak.")
            .unit(Unit.PIXEL)
            .readOnly()
            .commit(),

            UINT32_ELEMENT(expected).key('peak2Fwhm')
            .displayedName("Peak 2 FWHM")
            .description("FWHM of the 2nd peak.")
            .unit(Unit.PIXEL)
            .readOnly()
            .commit(),

            DOUBLE_ELEMENT(expected).key('peakRatio')
            .displayedName("Peak Ratio")
            .description("Amplitude of the 1st peak divided by amplitude of "
                         "the second peak.")
            .unit(Unit.NUMBER)
            .readOnly()
            .commit(),
        )

    def onEndOfStream(self, inputChannel):
        self.logger.info("End of Stream")
        self['inFrameRate'] = 0.
        self.updateState(State.ON)
        self['status'] = 'Idle'

    # Overrides ImageProcessorBase.process_image
    def process_image(self, image_data, ts):
        if isinstance(image_data, np.ndarray):
            img = image_data
        elif isinstance(image_data, list):
            img = np.asarray(image_data)
        elif isinstance(image_data, ImageData):
            img = image_data.getData()
        else:
            raise RuntimeError(
                f"Unsupported input data type {type(image_data)}")
        zero_point = self['zeroPoint']
        roi = self['roi']

        if roi and len(roi) == 2 and roi[1] > roi[0] >= 0:
            low_x = roi[0]
            high_x = roi[1]
            if zero_point <= low_x or zero_point >= high_x:
                raise RuntimeError("zero_point is outside ROI.")

            if img.ndim == 2:
                # sum along y axis
                img_x = imageSumAlongY(img[:, low_x:high_x + 1])
            elif img.ndim == 1:
                img_x = img[low_x:high_x + 1]
            else:
                raise RuntimeError(f"{img.ndim}-d data are not supported")

        else:
            # No valid ROI
            low_x = 0
            img_x = imageSumAlongY(img)

        peaks = find_peaks(img_x, zero_point - low_x)

        h = Hash()
        h.set('peak1Value', peaks[0])
        h.set('peak1Position', low_x + peaks[1])
        h.set('peak1Fwhm', peaks[2])
        h.set('peak2Value', peaks[3])
        h.set('peak2Position', low_x + peaks[4])
        h.set('peak2Fwhm', peaks[5])
        if peaks[3] > 0.0:
            h.set('peakRatio', peaks[0] / peaks[3])
        self.set(h, ts)
