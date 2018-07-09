"""
Author: heisenb
Creation date: January, 2017, 05:21 PM
Copyright (c) European XFEL GmbH Hamburg. All rights reserved.
"""
import time

from karabo.bound import (
    KARABO_CLASSINFO, State, PythonDevice,
    ImageData, Schema, Unit, IMAGEDATA_ELEMENT, INPUT_CHANNEL, OUTPUT_CHANNEL,
    OVERWRITE_ELEMENT, UINT32_ELEMENT, Hash, FLOAT_ELEMENT, SLOT_ELEMENT,
    NODE_ELEMENT
)

from image_processing.image_running_mean import ImageRunningMean


@KARABO_CLASSINFO('ImageAverager', '2.0')
class ImageAverager(PythonDevice):

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

            SLOT_ELEMENT(expected).key('resetAverage')
                    .displayedName('Reset Average')
                    .description('Reset averaged image.')
                    .commit(),

            UINT32_ELEMENT(expected).key('nImages')
                    .displayedName('Number of Images')
                    .description('Number of images to be averaged.')
                    .unit(Unit.NUMBER)
                    .assignmentOptional().defaultValue(5)
                    .minInc(1)
                    .reconfigurable()
                    .commit(),

            FLOAT_ELEMENT(expected).key('frameRate')
                    .displayedName('Frame Rate')
                    .description('The actual frame rate.')
                    .unit(Unit.HERTZ)
                    .readOnly()
                    .commit(),

            FLOAT_ELEMENT(expected).key('latency')
                    .displayedName('Image Latency')
                    .description('The latency of the incoming image.'
                                 'Smaller values are closer to realtime.')
                    .unit(Unit.HERTZ)
                    .readOnly()
                    .commit(),
        )

    def __init__(self, configuration):
        # always call PythonDevice constructor first!
        super(ImageAverager, self).__init__(configuration)
        # Register channel callback
        self.KARABO_ON_DATA('input', self.onData)
        self.KARABO_ON_EOS('input', self.onEndOfStream)
        # Register additional slot
        self.KARABO_SLOT(self.resetAverage)
        # Get an instance of the mean calculator
        self.imageRunningMean = ImageRunningMean()
        # Variables for frames per second computation
        self.lastTime = None
        self.counter = 0

    def onData(self, data, metaData):
        """ This function will be called whenever a data token is availabe"""
        if self["state"] == State.PASSIVE:
            self.log.INFO("Start of Stream")
            self.updateState(State.ACTIVE)

        self.updateFrameRate()

        if data.has('data.image'):
            inputImage = data['data.image']
        elif data.has('image'):
            # To ensure backward compatibility
            # with older versions of cameras
            inputImage = data['image']
        else:
            self.log.DEBUG("Data contains no image at 'data.image'")
            return

        nImages = self['nImages']
        if nImages == 1:
            # No averaging needed
            h = Hash('data.image', inputImage)
            self.writeChannel('output', h)
            return

        # Compute latency
        header = inputImage.getHeader()
        if header.has('creationTime'):
            self['latency'] = time.time() - header['creationTime']

        # Compute average
        pixels = inputImage.getData()
        self.imageRunningMean.append(pixels, nImages)

        h = Hash('data.image', ImageData(self.imageRunningMean.runningMean))
        self.writeChannel('output', h)
        self.log.DEBUG('Averaged image sent to output channel')

    def onEndOfStream(self, inputChannel):
        self.log.INFO("End of Stream")
        self["frameRate"] = 0.
        self.updateState(State.PASSIVE)
        self.signalEndOfStream("output")

    def updateFrameRate(self):
        self.counter += 1
        currentTime = time.time()
        if self.lastTime is None:
            self.counter = 0
            self.lastTime = currentTime
        elif self.lastTime is not None and (currentTime - self.lastTime) > 1.:
            fps = self.counter / (currentTime - self.lastTime)
            self['frameRate'] = fps
            self.log.DEBUG('Acquisition rate %f Hz' % fps)
            self.counter = 0
            self.lastTime = currentTime

    def resetAverage(self):
        self.log.INFO('Reset image average and fps')
        self.imageRunningMean.clear()
        self['frameRate'] = 0
