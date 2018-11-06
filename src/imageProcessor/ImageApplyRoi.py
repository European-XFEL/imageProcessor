#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on June 5, 2018
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

from karabo.bound import (
    BOOL_ELEMENT, DOUBLE_ELEMENT, Hash, ImageData, IMAGEDATA_ELEMENT,
    INPUT_CHANNEL, KARABO_CLASSINFO, NODE_ELEMENT, OUTPUT_CHANNEL,
    OVERWRITE_ELEMENT, PythonDevice, Schema, State, Timestamp, Unit,
    VECTOR_INT32_ELEMENT,
)

from processing_utils.rate_calculator import RateCalculator


@KARABO_CLASSINFO("ImageApplyRoi", "2.2")
class ImageApplyRoi(PythonDevice):

    @staticmethod
    def expectedParameters(expected):
        data = Schema()
        (
            OVERWRITE_ELEMENT(expected).key("state")
                .setNewOptions(State.PASSIVE, State.ACTIVE)
                .setNewDefaultValue(State.PASSIVE)
                .commit(),

            NODE_ELEMENT(data).key("data")
                .displayedName("Data")
                .commit(),

            IMAGEDATA_ELEMENT(data).key("data.image")
                .displayedName("Image")
                .commit(),

            INPUT_CHANNEL(expected).key("input")
                .displayedName("Input")
                .dataSchema(data)
                .commit(),

            # Images should be dropped if processor is too slow
            OVERWRITE_ELEMENT(expected).key("input.onSlowness")
                .setNewDefaultValue("drop")
                .commit(),

            OUTPUT_CHANNEL(expected).key("output")
                .displayedName("Output")
                .dataSchema(data)
                .commit(),

            DOUBLE_ELEMENT(expected).key("frameRate")
                .displayedName("Frame Rate")
                .description("The actual frame rate.")
                .unit(Unit.HERTZ)
                .readOnly()
                .commit(),

            BOOL_ELEMENT(expected).key("disable")
                .description("Disable ROI")
                .assignmentOptional().defaultValue(False)
                .init()
                .commit(),

            VECTOR_INT32_ELEMENT(expected).key("roi")
                .displayedName("ROI")
                .description("The user-defined region of interest (ROI),"
                             " specified as [lowX, highX, lowY, highY].")
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

        # Variables for frames per second computation
        self.frame_rate = RateCalculator(refresh_interval=1.0)

    def initialization(self):
        """ This method will be called after the constructor. """
        roi = self["roi"]
        valid = self.validRoi(roi)
        if not valid:
            self.set("disable", True)
            self.log.ERROR("Initial ROI is invalid -> disabled")

    def preReconfigure(self, incomingReconfiguration):
        if incomingReconfiguration.has("roi"):
            roi = incomingReconfiguration["roi"]
            valid = self.validRoi(roi)
            if valid:
                self.set("disable", False)
                self.log.INFO("Applying new roi {}".format(roi))
            else:
                incomingReconfiguration.erase("roi")
                self.log.ERROR("New ROI is invalid -> rejected")

    def onData(self, data, metaData):
        if self.get("state") == State.PASSIVE:
            self.log.INFO("Start of Stream")
            self.updateState(State.ACTIVE)

        try:
            if data.has('data.image'):
                imageData = data['data.image']
            elif data.has('image'):
                # To ensure backward compatibility
                # with older versions of cameras
                imageData = data['image']
            else:
                self.log.DEBUG("data does not have any image")
                return

            ts = Timestamp.fromHashAttributes(
                metaData.getAttributes('timestamp'))
            self.processImage(imageData, ts)  # Process image

        except Exception as e:
            self.log.ERROR("Exception caught in onData: %s" % str(e))

    def onEndOfStream(self, inputChannel):
        self.log.INFO("End of Stream")
        self.set("frameRate", 0.)
        # Signals end of stream
        self.signalEndOfStream("output")
        self.updateState(State.PASSIVE)

    def processImage(self, imageData, ts):
        disable = self.get("disable")
        roi = self.get("roi")

        self.refreshFrameRate()

        try:
            if disable:
                self.log.DEBUG("ROI disabled!")
                self.writeChannel("output", Hash("data.image", imageData), ts)
                self.log.DEBUG("Original image copied to output channel")
                return

            lowX = roi[0]
            highX = roi[1]
            lowY = roi[2]
            highY = roi[3]
            data = imageData.getData()  # np.ndarray
            yOff, xOff = imageData.getROIOffsets()  # input image offset
            yOff += lowY  # output image offset
            xOff += lowX  # output image offset
            croppedImage = ImageData(data[lowY:highY, lowX:highX])
            croppedImage.setROIOffsets((yOff, xOff))
            self.writeChannel("output", Hash("data.image", croppedImage), ts)

        except Exception as e:
            self.log.WARN("In processImage: %s" % str(e))
            return

    def validRoi(self, roi):
        if roi[0] < 0 or roi[1] < roi[0]:
            return False
        if roi[2] < 0 or roi[3] < roi[2]:
            return False

        return True

    def refreshFrameRate(self):
        self.frame_rate.update()
        fps = self.frame_rate.refresh()
        if fps:
            self['frameRate'] = fps
            self.log.DEBUG('Input rate %f Hz' % fps)
