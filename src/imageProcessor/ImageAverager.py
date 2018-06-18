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
)

from image_processing.image_running_mean import ImageRunningMean


@KARABO_CLASSINFO('ImageAverager', '2.0')
class ImageAverager(PythonDevice):

    @staticmethod
    def expectedParameters(expected):
        inputSchema = Schema()
        outputSchema = Schema()
        (
            OVERWRITE_ELEMENT(expected).key("state")
                .setNewOptions(State.PASSIVE, State.ACTIVE)
                .setNewDefaultValue(State.PASSIVE)
                .commit(),

            IMAGEDATA_ELEMENT(inputSchema).key('image')
                .commit(),

            INPUT_CHANNEL(expected).key('input')
                .displayedName('Input')
                .dataSchema(inputSchema)
                .commit(),

            IMAGEDATA_ELEMENT(outputSchema).key('image')
                .commit(),

            OUTPUT_CHANNEL(expected).key('output')
                .displayedName('Output')
                .dataSchema(outputSchema)
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

        nImages = self['nImages']
        if nImages == 1:
            # No averaging needed
            self.writeChannel('output', data)
            return

        inputImage = data['image']

        # Compute latency
        header = inputImage.getHeader()
        if header.has('creationTime'):
            self['latency'] = time.time() - header['creationTime']

        # Compute average
        pixels = inputImage.getData()
        self.imageRunningMean.append(pixels, nImages)

        h = Hash('image', ImageData(self.imageRunningMean.runningMean))
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
