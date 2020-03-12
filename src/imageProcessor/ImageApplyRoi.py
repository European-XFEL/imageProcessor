#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on June 5, 2018
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

from karabo.bound import (
    BOOL_ELEMENT, ImageData, KARABO_CLASSINFO, State, Timestamp,
    VECTOR_INT32_ELEMENT
)

try:
    from .common import ImageProcOutputInterface
    from .ImageProcessorBase import ImageProcessorBase
except ImportError:
    from imageProcessor.common import ImageProcOutputInterface
    from imageProcessor.ImageProcessorBase import ImageProcessorBase


@KARABO_CLASSINFO("ImageApplyRoi", "2.6")
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
        super(ImageApplyRoi, self).__init__(configuration)

        # Register call-backs
        self.KARABO_ON_DATA("input", self.onData)
        self.KARABO_ON_EOS("input", self.onEndOfStream)

        self.registerInitialFunction(self.initialization)

    def initialization(self):
        """ This method will be called after the constructor. """
        roi = self["roi"]
        valid = self.valid_roi(roi)
        if not valid:
            self['disable'] = True
            self.log.ERROR("Initial ROI is invalid -> disabled")

    def preReconfigure(self, incomingReconfiguration):
        # always call ImageProcessorBase preReconfigure first!
        super(ImageApplyRoi, self).preReconfigure(incomingReconfiguration)

        if incomingReconfiguration.has('roi'):
            roi = incomingReconfiguration['roi']
            valid = self.valid_roi(roi)
            if valid:
                self['disable'] = False
                self.log.INFO("Applying new roi {}".format(roi))
            else:
                incomingReconfiguration.erase("roi")
                self.log.ERROR("New ROI is invalid -> rejected")

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
        except Exception as e:
            msg = "Exception caught in onData: {}".format(e)
            self.update_count(error=True, msg=msg)
            return

        ts = Timestamp.fromHashAttributes(
            metaData.getAttributes('timestamp'))

        # NB updateOutputSchema must be called in process_image
        #    on cropped_image
        self.process_image(image_data, ts)  # Process image

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
            disable = self['disable']
            if disable:
                self.log.DEBUG("ROI disabled!")
                self.writeImageToOutputs(image_data, ts)
                self.log.DEBUG("Original image copied to output channel")
                self.update_count()  # Success
                return

            low_x, high_x, low_y, high_y = self['roi']

            data = image_data.getData()  # np.ndarray
            y_off, x_off = image_data.getROIOffsets()  # input image offset
            y_off += low_y  # output image offset
            x_off += low_x  # output image offset
            cropped_image = ImageData(data[low_y:high_y, low_x:high_x])
            cropped_image.setROIOffsets((y_off, x_off))

            if cropped_image.getDimensions() != self.shape:
                self.updateOutputSchema(cropped_image)

            self.writeImageToOutputs(cropped_image, ts)
            self.update_count()  # Success
            return

        except Exception as e:
            msg = "Exception caught in process_image: {}".format(e)
            self.update_count(error=True, msg=msg)

    @staticmethod
    def valid_roi(roi):
        if roi[0] < 0 or roi[1] < roi[0]:
            return False
        if roi[2] < 0 or roi[3] < roi[2]:
            return False

        return True
