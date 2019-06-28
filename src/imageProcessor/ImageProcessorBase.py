#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on March 21, 2019
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

from karabo.bound import (
    DOUBLE_ELEMENT, Hash, IMAGEDATA_ELEMENT, INPUT_CHANNEL, KARABO_CLASSINFO,
    NODE_ELEMENT, OVERWRITE_ELEMENT, PythonDevice, Schema, SLOT_ELEMENT,
    State, UINT32_ELEMENT, Unit, VECTOR_STRING_ELEMENT
)

from processing_utils.rate_calculator import RateCalculator

try:
    from .common import ErrorCounter
except ImportError:
    from imageProcessor.common import ErrorCounter


@KARABO_CLASSINFO("ImageProcessorBase", "2.5")
class ImageProcessorBase(PythonDevice):

    # TODO: move in this class the onData registration and boilerplate code

    @staticmethod
    def expectedParameters(expected):
        data = Schema()
        (
            OVERWRITE_ELEMENT(expected).key('state')
            .setNewOptions(State.ON, State.PROCESSING, State.ERROR)
            .setNewDefaultValue(State.ON)
            .commit(),

            VECTOR_STRING_ELEMENT(expected).key("interfaces")
            .displayedName("Interfaces")
            .readOnly()
            .initialValue(["Processor"])
            .commit(),

            NODE_ELEMENT(data).key('data')
            .displayedName("Data")
            .commit(),

            IMAGEDATA_ELEMENT(data).key('data.image')
            .commit(),

            INPUT_CHANNEL(expected).key('input')
            .displayedName("Input")
            .dataSchema(data)
            .commit(),

            # Images should be dropped if processor is too slow
            OVERWRITE_ELEMENT(expected).key('input.onSlowness')
            .setNewDefaultValue("drop")
            .commit(),

            DOUBLE_ELEMENT(expected).key('inFrameRate')
            .displayedName('Input Frame Rate')
            .description('The input frame rate.')
            .unit(Unit.HERTZ)
            .readOnly()
            .commit(),

            NODE_ELEMENT(expected).key('errorCounter')
            .displayedName("Error Count")
            .commit(),

            UINT32_ELEMENT(expected).key('errorCounter.count')
            .displayedName("Error Count")
            .description("Number of errors.")
            .unit(Unit.COUNT)
            .readOnly().initialValue(0)
            .commit(),

            UINT32_ELEMENT(expected).key('errorCounter.windowSize')
            .displayedName("Window Size")
            .description("Size of the sliding window for counting errors.")
            .unit(Unit.NUMBER)
            .assignmentOptional().defaultValue(100)
            .minInc(10).maxInc(6000)
            .init()
            .commit(),

            DOUBLE_ELEMENT(expected).key('errorCounter.threshold')
            .displayedName("Threshold")
            .description("Threshold on the ratio errors/total counts, "
                         "for setting the alarmState.")
            .unit(Unit.NUMBER)
            .assignmentOptional().defaultValue(0.1)
            .minInc(0.001).maxInc(1.)
            .reconfigurable()
            .commit(),

            DOUBLE_ELEMENT(expected).key('errorCounter.epsilon')
            .displayedName("Epsilon")
            .description("The device will enter the alarm condition when "
                         "'fraction' exceeds threshold + epsilon, and will "
                         "leave it when fraction goes below threshold -"
                         " epsilon.")
            .expertAccess()
            .unit(Unit.NUMBER)
            .assignmentOptional().defaultValue(0.01)
            .minInc(0.001).maxInc(1.)
            .reconfigurable()
            .commit(),

            DOUBLE_ELEMENT(expected).key('errorCounter.fraction')
            .displayedName("Error Fraction")
            .description("Fraction of errors in the specified window.")
            .readOnly().initialValue(0.)
            .commit(),

            UINT32_ELEMENT(expected).key('errorCounter.alarmCondition')
            .displayedName("Alarm Condition")
            .description("True if the fraction of errors exceeds the "
                         "threshold.")
            .readOnly().initialValue(0)
            .alarmHigh(0).info("Error fraction above threshold.")
            .needsAcknowledging(False)
            .commit(),

            SLOT_ELEMENT(expected).key('resetError')
            .displayedName('Reset')
            .description("Reset error count.")
            .commit(),
        )

    def __init__(self, configuration):
        # always call PythonDevice constructor first!
        super(ImageProcessorBase, self).__init__(configuration)

        if configuration.has('errorCounter.windowSize'):
            window_size = configuration['errorCounter.windowSize']
            self.error_counter = ErrorCounter(window_size=int(window_size))
        else:
            self.error_counter = ErrorCounter()

        if configuration.has('errorCounter.threshold'):
            self.error_counter.threshold = configuration[
                'errorCounter.threshold']

        if configuration.has('errorCounter.epsilon'):
            self.error_counter.epsilon = configuration[
                'errorCounter.epsilon']

        # Variables for frames per second computation
        self.frame_rate_in = RateCalculator(refresh_interval=1.0)

        # Register additional slots
        self.KARABO_SLOT(self.resetError)

    def preReconfigure(self, configuration):
        if configuration.has('errorCounter.threshold'):
            self.error_counter.threshold = configuration[
                'errorCounter.threshold']

        if configuration.has('errorCounter.epsilon'):
            self.error_counter.epsilon = configuration[
                'errorCounter.epsilon']

    def resetError(self):
        self.log.INFO("Reset error counter")
        self.error_counter.clear()
        self.updateState(State.ON)

    def update_alarm(self, error=False, msg=""):
        self.error_counter.append(error)
        h = Hash()

        if self['errorCounter.count'] != self.error_counter.count_error:
            # Update in device only if changed
            h['errorCounter.count'] = self.error_counter.count_error

        if self['errorCounter.fraction'] != self.error_counter.fraction:
            # Update in device only if changed
            h['errorCounter.fraction'] = self.error_counter.fraction

        if not error:
            if self['status'] != "PROCESSING":
                h['status'] = "PROCESSING"
        elif not self['errorCounter.alarmCondition'] and msg:
            # Only update if not yet in ALARM
            h['status'] = msg
            self.log.ERROR(msg)

        if self['errorCounter.alarmCondition'] != self.error_counter.alarm:
            # Update in device only if changed
            h['errorCounter.alarmCondition'] = self.error_counter.alarm

        if not h.empty():
            self.set(h)

    def refresh_frame_rate_in(self):
        self.frame_rate_in.update()
        fps_in = self.frame_rate_in.refresh()
        if fps_in:
            self['inFrameRate'] = fps_in
            self.log.DEBUG("Input rate {} Hz".format(fps_in))
