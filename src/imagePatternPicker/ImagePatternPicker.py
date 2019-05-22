#############################################################################
# Author: parenti
# Created on April 16, 2019, 02:56 PM
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

from karabo.bound import (
    DOUBLE_ELEMENT, INPUT_CHANNEL, KARABO_CLASSINFO, IMAGEDATA_ELEMENT,
    NODE_ELEMENT, OUTPUT_CHANNEL, OVERWRITE_ELEMENT, PythonDevice, Schema,
    State, Timestamp, UINT32_ELEMENT, UINT64_ELEMENT, Unit
)

from processing_utils.rate_calculator import RateCalculator


@KARABO_CLASSINFO("ImagePatternPicker", "2.0")
class ImagePatternPicker(PythonDevice):

    @staticmethod
    def expectedParameters(expected):
        data_in = Schema()
        data_out = Schema()
        (
            OVERWRITE_ELEMENT(expected).key('state')
            .setNewOptions(State.ON, State.PROCESSING, State.ERROR)
            .setNewDefaultValue(State.ON)
            .commit(),

            UINT32_ELEMENT(expected).key("nBunchPatterns")
            .displayedName("# Bunch Patterns")
            .description("Number of bunch patterns.")
            .assignmentOptional().defaultValue(2)
            .minInc(1)
            .reconfigurable()
            .commit(),

            UINT32_ELEMENT(expected).key("patternOffset")
            .displayedName("Pattern Offset")
            .description("Image will be forwarded to the output if its "
                         "trainId satisfies the following relation: "
                         "(trainId%nBunchPatterns) ==  patternOffset.")
            .assignmentOptional().defaultValue(1)
            .reconfigurable()
            .commit(),

            DOUBLE_ELEMENT(expected).key('inFrameRate')
            .displayedName('Input Frame Rate')
            .description('The input frame rate.')
            .unit(Unit.HERTZ)
            .readOnly()
            .commit(),

            DOUBLE_ELEMENT(expected).key('outFrameRate')
            .displayedName('Output Frame Rate')
            .description('The output frame rate.')
            .unit(Unit.HERTZ)
            .readOnly()
            .commit(),

            NODE_ELEMENT(data_in).key('data')
            .displayedName("Data")
            .commit(),

            IMAGEDATA_ELEMENT(data_in).key('data.image')
            .commit(),

            INPUT_CHANNEL(expected).key('input')
            .displayedName("Input")
            .dataSchema(data_in)
            .commit(),

            # Images should be dropped if processor is too slow
            OVERWRITE_ELEMENT(expected).key('input.onSlowness')
            .setNewDefaultValue("drop")
            .commit(),

            NODE_ELEMENT(data_out).key('data')
            .displayedName("Data")
            .commit(),

            IMAGEDATA_ELEMENT(data_out).key('data.image')
            .commit(),

            UINT64_ELEMENT(data_out).key('data.trainId')
            .displayedName('Train ID')
            .readOnly()
            .commit(),

            OUTPUT_CHANNEL(expected).key("output")
            .displayedName("Output")
            .dataSchema(data_out)
            .commit(),
        )

    def __init__(self, configuration):
        # always call PythonDevice constructor first!
        super(ImagePatternPicker, self).__init__(configuration)
        # Define the first function to be called after the constructor has
        # finished
        self.registerInitialFunction(self.initialization)

    def initialization(self):
        # Register call-backs
        self.KARABO_ON_DATA("input", self.onData)
        self.KARABO_ON_EOS("input", self.onEndOfStream)

        # Variables for frames per second computation
        self.frame_rate_in = RateCalculator(refresh_interval=1.0)
        self.frame_rate_out = RateCalculator(refresh_interval=1.0)

    def onData(self, data, metaData):
        if self['state'] == State.ON:
            self.log.INFO("Start of Stream")
            self.updateState(State.PROCESSING)

        self.refresh_frame_rate_in()

        ts = Timestamp.fromHashAttributes(
            metaData.getAttributes('timestamp'))
        train_id = ts.getTrainId()
        if (train_id % self['nBunchPatterns']) == self['patternOffset']:
            data['data.trainId'] = train_id
            self.writeChannel('output', data, ts)
            self.refresh_frame_rate_out()

    def onEndOfStream(self, inputChannel):
        self.log.INFO("onEndOfStream called")
        self['inFrameRate'] = 0.
        self['outFrameRate'] = 0.
        # Signals end of stream
        self.signalEndOfStream("output")
        self.updateState(State.ON)

    def refresh_frame_rate_in(self):
        self.frame_rate_in.update()
        fps_in = self.frame_rate_in.refresh()
        if fps_in:
            self['inFrameRate'] = fps_in
            self.log.DEBUG("Input rate {} Hz".format(fps_in))

    def refresh_frame_rate_out(self):
        self.frame_rate_out.update()
        fps_out = self.frame_rate_out.refresh()
        if fps_out:
            self['outFrameRate'] = fps_out
            self.log.DEBUG("Output rate {} Hz".format(fps_out))
