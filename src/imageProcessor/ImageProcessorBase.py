#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on March 21, 2019
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################

from karabo.bound import (
    DOUBLE_ELEMENT, IMAGEDATA_ELEMENT, INPUT_CHANNEL, KARABO_CLASSINFO,
    NODE_ELEMENT, OVERWRITE_ELEMENT, SLOT_ELEMENT, STRING_ELEMENT,
    UINT32_ELEMENT, VECTOR_STRING_ELEMENT, Hash, PythonDevice, Schema, State,
    Timestamp, Unit)
from processing_utils.rate_calculator import RateCalculator

from ._version import version as deviceVersion
from .common import ErrorCounter


@KARABO_CLASSINFO("ImageProcessorBase", deviceVersion)
class ImageProcessorBase(PythonDevice):

    @staticmethod
    def expectedParameters(expected):
        data = Schema()
        (
            OVERWRITE_ELEMENT(expected).key('state')
            .setNewOptions(State.ON, State.PROCESSING, State.ERROR)
            .setNewDefaultValue(State.ON)
            .commit(),

            STRING_ELEMENT(expected).key("imagePath")
            .displayedName("Image Path")
            .description("Input image path.")
            .assignmentOptional().defaultValue("data.image")
            .expertAccess()
            .init()
            .commit(),

            VECTOR_STRING_ELEMENT(expected).key("interfaces")
            .displayedName("Interfaces")
            .readOnly()
            .defaultValue(["Processor"])
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
            .readOnly().defaultValue(0)
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
                         "for setting the warn condition.")
            .unit(Unit.NUMBER)
            .assignmentOptional().defaultValue(0.1)
            .minInc(0.001).maxInc(1.0)
            .reconfigurable()
            .commit(),

            DOUBLE_ELEMENT(expected).key('errorCounter.epsilon')
            .displayedName("Epsilon")
            .description("The device will enter the warn condition when "
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
            .readOnly().defaultValue(0.)
            .commit(),

            UINT32_ELEMENT(expected).key('errorCounter.warnCondition')
            .displayedName("Warn Condition")
            .description("True if the fraction of errors exceeds the "
                         "threshold.")
            .readOnly().defaultValue(0)
            .warnHigh(0).info("Error fraction above threshold.")
            .needsAcknowledging(False)
            .commit(),

            SLOT_ELEMENT(expected).key('resetError')
            .displayedName('Reset')
            .description("Reset error count.")
            .commit(),
        )

    def __init__(self, configuration):
        # always call PythonDevice constructor first!
        super().__init__(configuration)

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

        configuration['status'] = 'Idle'

        # Variables for frames per second computation
        self.frame_rate_in = RateCalculator(refresh_interval=1.0)

        # Register additional slots
        self.KARABO_SLOT(self.resetError)

        # Register call-backs
        self.KARABO_ON_DATA("input", self.onData)

    def preReconfigure(self, configuration):
        need_refresh = False

        if configuration.has('errorCounter.threshold'):
            self.error_counter.threshold = configuration[
                'errorCounter.threshold']
            need_refresh = True

        if configuration.has('errorCounter.epsilon'):
            self.error_counter.epsilon = configuration[
                'errorCounter.epsilon']
            need_refresh = True

        if need_refresh:
            # warn level has to be re-evaluated
            h = Hash()
            self.evaluate_warn(h)
            if not h.empty():
                self.set(h)

    def resetError(self):
        self.log.INFO("Called 'Reset Error'")

        h = Hash('status', "Called 'Reset Error'")
        self.error_counter.clear()
        self.evaluate_warn(h)
        self.set(h)

        if self['state'] != State.ON:
            self.updateState(State.ON)

    def update_count(self, error=False, status="Processing"):
        """ Update success/error counting, as well as warn level.

        :param error: depending on this flag, one count will be added either
        to errors, or to successes
        :param status: the new status to be set and logged
        :return:
        """
        h = Hash()

        self.error_counter.append(error)
        self.evaluate_warn(h)

        if self['status'] != status:
            h['status'] = status
            if error:
                self.log.ERROR(status)
            else:
                self.log.INFO(status)

        if not h.empty():
            self.set(h)

    def evaluate_warn(self, h):
        """ Evaluate the warn condition, and return it in a Hash

        :param h: the device reconfiguration Hash
        :return:
        """
        if self['errorCounter.count'] != self.error_counter.count_error:
            # Update in device only if changed
            h['errorCounter.count'] = self.error_counter.count_error

        if self['errorCounter.fraction'] != self.error_counter.fraction:
            # Update in device only if changed
            h['errorCounter.fraction'] = self.error_counter.fraction

        if self['errorCounter.warnCondition'] != self.error_counter.warn:
            # Update in device only if changed
            h['errorCounter.warnCondition'] = self.error_counter.warn

    def refresh_frame_rate_in(self):
        self.frame_rate_in.update()
        fps_in = self.frame_rate_in.refresh()
        if fps_in:
            self['inFrameRate'] = fps_in
            self.log.DEBUG(f"Input rate {fps_in} Hz")

    def onData(self, data, metaData):
        self.refresh_frame_rate_in()

        if self['state'] == State.ON:
            self.log.INFO("Start of Stream")
            self.updateState(State.PROCESSING)

        try:
            image_path = self['imagePath']
            if data.has(image_path):
                image_data = data[image_path]
            else:
                raise RuntimeError("Data does not contain any image")

            ts = Timestamp.fromHashAttributes(
                metaData.getAttributes('timestamp'))

            # Process image
            proc_image_data = self.process_image(image_data, ts)

            if "has_output_channels" in dir(self):
                shape = proc_image_data.getData().shape
                k_type = proc_image_data.getType()
                if shape != self.shape or k_type == self.kType:
                    self.updateOutputSchema(proc_image_data)

                # Write to the output channels
                self.writeImageToOutputs(proc_image_data, ts)

                self.refresh_frame_rate_out()

            self.update_count()  # Success

        except Exception as e:
            msg = f"Exception caught in onData: {e}"
            self.update_count(error=True, status=msg)

    def process_image(self, image_data, ts):
        raise NotImplementedError(
            "This function must be overridden in the derived class.")
