#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on November 14, 2018
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

from karabo.bound import (
    DOUBLE_ELEMENT, Hash, KARABO_CLASSINFO, State, Timestamp, UINT32_ELEMENT,
    Unit, VECTOR_UINT32_ELEMENT
)

from image_processing.image_processing import (
    imageSumAlongY, peakParametersEval
)

try:
    from .ImageProcessorBase import ImageProcessorBase
except ImportError:
    from imageProcessor.ImageProcessorBase import ImageProcessorBase


def find_peaks(img_x, zero_point):
    """Find two peaks - one left one right - from zero_point"""
    value_1, pos_1, fwhm_1 = peakParametersEval(img_x[zero_point::-1])
    value_2, pos_2, fwhm_2 = peakParametersEval(img_x[zero_point:])
    pos_1 = zero_point - pos_1
    pos_2 += zero_point

    return value_1, pos_1, fwhm_1, value_2, pos_2, fwhm_2


@KARABO_CLASSINFO("TwoPeakFinder", "2.6")
class TwoPeakFinder(ImageProcessorBase):

    def __init__(self, configuration):
        # always call superclass constructor first!
        super(TwoPeakFinder, self).__init__(configuration)

        # Register call-backs
        self.KARABO_ON_DATA("input", self.onData)
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

    ##############################################
    #   Implementation of Callbacks              #
    ##############################################

    def onData(self, data, metaData):
        if self['state'] == State.ON:
            self.log.INFO("Start of Stream")
            self.updateState(State.PROCESSING)

        try:
            if data.has('data.image'):
                image_data = data['data.image']
            elif data.has('image'):
                # To ensure backward compatibility
                # with older versions of cameras
                image_data = data['image']
            else:
                raise RuntimeError("data does not contain any image")

            ts = Timestamp.fromHashAttributes(
                metaData.getAttributes('timestamp'))
            self.process_image(image_data, ts)  # Process image

        except Exception as e:
            msg = "Exception caught in onData: {}".format(e)
            self.update_warn(error=True, msg=msg)

    def onEndOfStream(self, inputChannel):
        self.log.INFO("End of Stream")
        self['inFrameRate'] = 0.
        self.updateState(State.ON)
        self['status'] = 'ON'

    ##############################################
    #   Implementation of process_image          #
    ##############################################

    def process_image(self, image_data, ts):
        self.refresh_frame_rate_in()

        try:
            img = image_data.getData()  # np.ndarray
            zero_point = self['zeroPoint']
            roi = self['roi']

            if roi and len(roi) == 2 and roi[1] > roi[0] >= 0:
                low_x = roi[0]
                high_x = roi[1]
                if zero_point <= low_x or zero_point >= high_x:
                    raise RuntimeError("zero_point is outside ROI.")

                # sum along y axis
                img_x = imageSumAlongY(img[:, low_x:high_x+1])
            else:
                # No valid ROI
                low_x = 0
                img_x = imageSumAlongY(img)

            peaks = find_peaks(img_x, zero_point-low_x)

            h = Hash()
            h.set('peak1Value', peaks[0])
            h.set('peak1Position', low_x + peaks[1])
            h.set('peak1Fwhm', peaks[2])
            h.set('peak2Value', peaks[3])
            h.set('peak2Position', low_x + peaks[4])
            h.set('peak2Fwhm', peaks[5])
            if peaks[3] > 0.0:
                h.set('peakRatio', peaks[0]/peaks[3])
            self.set(h, ts)

            self.update_warn()  # Success

        except Exception as e:
            msg = "Exception caught in process_image: {}".format(e)
            self.update_warn(error=True, msg=msg)
