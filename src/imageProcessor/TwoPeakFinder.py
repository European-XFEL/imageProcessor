#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on November 27, 2015
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

from karabo.bound import (
    DOUBLE_ELEMENT, IMAGEDATA_ELEMENT, INPUT_CHANNEL, KARABO_CLASSINFO,
    NODE_ELEMENT, OVERWRITE_ELEMENT, PythonDevice, Schema, State, Timestamp,
    UINT32_ELEMENT, Unit
)

from image_processing.image_processing import (
    imageSumAlongY, peakParametersEval
)

from processing_utils.rate_calculator import RateCalculator


@KARABO_CLASSINFO("TwoPeakFinder", "2.2")
class TwoPeakFinder(PythonDevice):

    def __init__(self, configuration):
        # always call PythonDevice constructor first!
        super(TwoPeakFinder, self).__init__(configuration)

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
            OVERWRITE_ELEMENT(expected).key('state')
                .setNewOptions(State.PASSIVE, State.ACTIVE)
                .setNewDefaultValue(State.PASSIVE)
                .commit(),

            NODE_ELEMENT(data).key('data')
                .displayedName('Data')
                .commit(),

            IMAGEDATA_ELEMENT(data).key('data.image')
                .displayedName('Image')
                .commit(),

            INPUT_CHANNEL(expected).key('input')
                .displayedName('Input')
                .dataSchema(data)
                .commit(),

            # Images should be dropped if processor is too slow
            OVERWRITE_ELEMENT(expected).key('input.onSlowness')
                .setNewDefaultValue('drop')
                .commit(),

            DOUBLE_ELEMENT(expected).key('frameRate')
                .displayedName('Frame Rate')
                .description('The actual frame rate.')
                .unit(Unit.HERTZ)
                .readOnly()
                .commit(),

            UINT32_ELEMENT(expected).key('zeroPoint')
                .displayedName('Zero Point')
                .description("Zero point for the two peaks finding.")
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
        )

    def initialization(self):
        """ This method will be called after the constructor. """

    ##############################################
    #   Implementation of Callbacks              #
    ##############################################

    def onData(self, data, metaData):
        if self['state'] == State.PASSIVE:
            self.log.INFO("Start of Stream")
            self.updateState(State.ACTIVE)

        try:
            if data.has('data.image'):
                image_data = data['data.image']
            elif data.has('image'):
                # To ensure backward compatibility
                # with older versions of cameras
                image_data = data['image']
            else:
                self.log.DEBUG("Data does not have any image")
                return

            ts = Timestamp.fromHashAttributes(
                metaData.getAttributes('timestamp'))
            self.process_image(image_data, ts)  # Process image

        except Exception as e:
            self.log.ERROR("Exception caught in onData: {}".format(e))

    def onEndOfStream(self, inputChannel):
        self.log.INFO("End of Stream")
        self['frameRate'] = 0.
        # Signals end of stream
        self.signalEndOfStream('output')
        self.updateState(State.PASSIVE)

    ##############################################
    #   Implementation of processImage           #
    ##############################################

    def process_image(self, image_data, ts):
        self.refresh_frame_rate()

        try:
            img = image_data.getData()  # np.ndarray
            imgX = imageSumAlongY(img)  # sum along y axis
            zeroPoint = self['zeroPoint']

            peak_value_1, peak_pos_1, fwhm_1 = peakParametersEval(
                imgX[:zeroPoint])
            peak_value_2, peak_pos_2, fwhm_2 = peakParametersEval(
                imgX[zeroPoint:])

            self['peak1Value'] = peak_value_1
            self['peak1Position'] = peak_pos_1
            self['peak1Fwhm'] = fwhm_1
            self['peak2Value'] = peak_value_2
            self['peak2Position'] = peak_pos_2
            self['peak2Fwhm'] = fwhm_2

        except Exception as e:
            self.log.ERROR("Exception caught in processImage: {}".format(e))

    def refresh_frame_rate(self):
        self.frame_rate.update()
        fps = self.frame_rate.refresh()
        if fps:
            self['frameRate'] = fps
            self.log.DEBUG('Input rate {} Hz'.format(fps))
