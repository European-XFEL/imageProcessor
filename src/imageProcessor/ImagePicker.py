#############################################################################
# Author: gabriele.giovanetti@xfel.eu
# Created on September 7, 2018, 12:00 PM
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

from collections import deque

from threading import Lock

from karabo.bound import (
    DOUBLE_ELEMENT, INT32_ELEMENT,  IMAGEDATA_ELEMENT, INPUT_CHANNEL,
    KARABO_CLASSINFO, NODE_ELEMENT, OUTPUT_CHANNEL, OVERWRITE_ELEMENT,
    PythonDevice, Schema, State, Timestamp, Unit, UINT32_ELEMENT,
)

from .common import FrameRate


@KARABO_CLASSINFO("ImagePicker", "2.2")
class ImagePicker(PythonDevice):
    """
    This device has two input channels (inputImage and inputTrainid).
    inputImage expects an image stream (e.g. from a camera)
    inputTrainId is used to get its timestamp
    images whose train id equals inputTrainId + trainIdOffset are forwarded to
    output channel, while others are discarded.

    """

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

            INPUT_CHANNEL(expected).key("inputImage")
                .displayedName("Input image")
                .dataSchema(data)
                .commit(),

            # Images should be dropped if processor is too slow
            OVERWRITE_ELEMENT(expected).key("inputImage.onSlowness")
                .setNewDefaultValue("drop")
                .commit(),

            INPUT_CHANNEL(expected).key("inputTrainId")
                .displayedName("Input Train Id")
                .dataSchema(Schema())
                .commit(),

            # Images should be dropped if processor is too slow
            OVERWRITE_ELEMENT(expected).key("inputTrainId.onSlowness")
                .setNewDefaultValue("drop")
                .commit(),

            OUTPUT_CHANNEL(expected).key("output")
                .displayedName("Output")
                .dataSchema(data)
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

            INT32_ELEMENT(expected).key("trainIdOffset")
                .displayedName("Train ID Offset")
                .description("Positive: output image train id is greater than "
                             "input train Id (delay). "
                             "Negative: output image train id is lower than "
                             "input train (advance)")
                .assignmentOptional().defaultValue(5)
                .init()
                .commit(),

            UINT32_ELEMENT(expected).key("imgBufferSize")
                .displayedName("Images buffer size")
                .description("Number of image to be kept waitng for "
                             "matching train id")
                .minInc(1)
                .assignmentOptional().defaultValue(5)
                .init()
                .commit(),

            UINT32_ELEMENT(expected).key("trainidBufferSize")
                .displayedName("Train Ids buffer size")
                .description("Number of train ids to be kept waitng for image "
                             "with matching train id")
                .assignmentOptional().defaultValue(5)
                .init()
                .commit(),

        )

    def __init__(self, configuration):
        # always call superclass constructor first!
        super(ImagePicker, self).__init__(configuration)

        # frames per second
        self.lastTime = None
        self.counter = 0

        self.imageBuffer = None
        self.trainidBuffer = None
        self.buffer_lock = Lock()

        self.isChannelActive = {'inputImage': False, 'inputTrainId': False}

        # Register call-backs
        self.KARABO_ON_DATA("inputImage", self.onDataImage)
        self.KARABO_ON_EOS("inputImage", self.onEndOfStream)
        self.KARABO_ON_DATA("inputTrainId", self.onDataTrainId)
        self.KARABO_ON_EOS("inputTrainId", self.onEndOfStream)

        self.registerInitialFunction(self.initialization)

        # Variables for frames per second computation
        self.frameRateIn = FrameRate()
        self.frameRateOut = FrameRate()

    def initialization(self):
        """ This method will be called after the constructor. """
        self.imageBuffer = deque(maxlen=self.get("imgBufferSize"))
        self.trainidBuffer = deque(maxlen=self.get("trainidBufferSize"))

    def isActive(self):
        return any(self.isChannelActive.values())

    def onDataImage(self, data, metaData):
        if self.imageBuffer is None:
            return

        self.isImageInputActive = True
        if self.get("state") == State.PASSIVE:
            self.log.INFO("Start of Image Stream")
            self.updateState(State.ACTIVE)

        self.frameRateIn.update()
        if self.frameRateIn.elapsedTime() >= 1.0:
            fpsIn = self.frameRateIn.rate()
            self['inFrameRate'] = fpsIn
            self.log.DEBUG('Input rate %f Hz' % fpsIn)
            self.frameRateIn.reset()

        try:
            ts = Timestamp.fromHashAttributes(
                metaData.getAttributes('timestamp'))

            with self.buffer_lock:
                self.imageBuffer.append({'ts': ts, 'data': data})

            self.searchForMatch()

        except Exception as e:
            self.log.ERROR("Exception caught in onData: %s" % str(e))

    def onDataTrainId(self, data, metaData):
        if self.trainidBuffer is None:
            return

        self.isChannelActive['inputTrainId'] = True
        if self.get("state") == State.PASSIVE:
            self.log.INFO("Start of Train Id Stream")
            self.updateState(State.ACTIVE)

        ts = Timestamp.fromHashAttributes(
            metaData.getAttributes('timestamp'))
        tid = ts.getTrainId()

        with self.buffer_lock:
            self.trainidBuffer.append(tid)

        self.searchForMatch()

    def searchForMatch(self):
        """ output data if matching trainId is found"""
        match_found = False
        with self.buffer_lock:
            for img in self.imageBuffer:
                for tid in self.trainidBuffer:
                    if(img['ts'].getTrainId() ==
                       tid + self.get("trainIdOffset")):
                        self.writeChannel('output', img['data'],
                                          img['ts'])
                        self.frameRateOut.update()

        if self.frameRateOut.elapsedTime() >= 1.0:
            fpsOut = self.frameRateOut.rate()
            self['outFrameRate'] = fpsOut
            self.log.DEBUG('Output rate %f Hz' % fpsOut)
            self.frameRateOut.reset()

    def onEndOfStream(self, inputChannel):
        self.log.INFO("End of Stream on channel {}".format(inputChannel))

        self.isChannelActive[inputChannel] = False

        if inputChannel == 'imageInput':
            self['inFrameRate'] = 0
            self['outFrameRate'] = 0
            self.signalEndOfStream("output")

        if not self.isActive():
            # Signals end of stream
            self.updateState(State.PASSIVE)
