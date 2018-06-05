#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on June 5, 2018
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

import time

from karabo.bound import (
    KARABO_CLASSINFO, PythonDevice,
    BOOL_ELEMENT, DOUBLE_ELEMENT, IMAGEDATA_ELEMENT,
    INPUT_CHANNEL, NODE_ELEMENT, OUTPUT_CHANNEL,
    OVERWRITE_ELEMENT, SLOT_ELEMENT, VECTOR_INT32_ELEMENT,
    Hash, ImageData, Schema, State, Unit
)


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
                .reconfigurable()
                .commit(),

            VECTOR_INT32_ELEMENT(expected).key("roi")
                .displayedName("ROI")
                .description("The user-defined region of interest (ROI),"
                             " specified as [lowX, highX, lowY, highY].")
                .assignmentOptional().defaultValue([-1, -1, -1, -1])
                .minSize(4).maxSize(4)
                .reconfigurable()
                .commit(),

        )

    def __init__(self, configuration):
        # always call superclass constructor first!
        super(ImageApplyRoi, self).__init__(configuration)

        # frames per second
        self.lastTime = None
        self.counter = 0

        # Register call-backs
        self.KARABO_ON_DATA("input", self.onData)
        self.KARABO_ON_EOS("input", self.onEndOfStream)

        self.registerInitialFunction(self.initialization)

    def initialization(self):
        """ This method will be called after the constructor. """
        roi = self["roi"]
        valid = self.validRoi(roi)
        if not valid:
            self.set("disable", True)
            self.log.ERROR("ROI is invalid -> will be disabled")

    def preReconfigure(self, incomingReconfiguration):
        if incomingReconfiguration.has("roi"):
            roi = incomingReconfiguration["roi"]
            valid = self.validRoi(roi)
            if not valid:
                incomingReconfiguration.erase("roi")
                self.set("disable", True)
                self.log.ERROR("ROI is invalid -> will be disabled")

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

            self.processImage(imageData)  # Process image

        except Exception as e:
            self.log.ERROR("Exception caught in onData: %s" % str(e))

    def onEndOfStream(self, inputChannel):
        self.log.INFO("End of Stream")
        self.set("frameRate", 0.)
        # Signals end of stream
        self.signalEndOfStream("output")
        self.updateState(State.PASSIVE)

    def processImage(self, imageData):
        disable = self.get("disable")
        roi = self.get("roi")

        try:
            self.counter += 1
            currentTime = time.time()
            if self.lastTime is None:
                self.counter = 0
                self.lastTime = currentTime
            elif (self.lastTime is not None and
                  (currentTime - self.lastTime) > 1.):
                fps = self.counter / (currentTime - self.lastTime)
                self.set("frameRate", fps)
                self.log.DEBUG("Acquisition rate %f Hz" % fps)
                self.counter = 0
                self.lastTime = currentTime
        except Exception as e:
            self.log.ERROR("Exception caught in processImage: %s" % str(e))

        try:
            if disable:
                self.log.DEBUG("ROI disabled!")
                self.writeChannel("output", Hash("data.image", imageData))
                self.log.DEBUG("Original image copied to output channel")
                return

            dims = imageData.getDimensions()
            imageHeight = dims[0]
            imageWidth = dims[1]

            lowX = roi[0]
            highX = roi[1]
            lowY = roi[2]
            highY = roi[3]
            data = imageData.getData()  # np.ndarray
            croppedImage = ImageData(data[lowY:highY, lowX:highX])
            self.writeChannel("output", Hash("data.image", croppedImage))

        except Exception as e:
            self.log.WARN("In processImage: %s" % str(e))
            return

    def validRoi(self, roi):
        if roi[0] < 0 or roi[1] < roi[0]:
            return False
        if roi[2] < 0 or roi[3] < roi[2]:
            return False

        return True
