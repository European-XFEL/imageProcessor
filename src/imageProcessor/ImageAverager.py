"""
Author: heisenb
Creation date: January, 2017, 05:21 PM
Copyright (c) European XFEL GmbH Hamburg. All rights reserved.
"""
import numpy as np
import time

from karabo.bound import (
    BOOL_ELEMENT, FLOAT_ELEMENT, Hash, ImageData, IMAGEDATA_ELEMENT,
    INPUT_CHANNEL, KARABO_CLASSINFO, NODE_ELEMENT, OUTPUT_CHANNEL,
    OVERWRITE_ELEMENT, PythonDevice, Schema, SLOT_ELEMENT, State, Timestamp,
    UINT32_ELEMENT, Unit
)

from image_processing.image_running_mean import ImageRunningMean


class FrameRate:
    def __init__(self, type='input'):
        self.counter = 0
        self.lastTime = time.time()
        self.type = type

    def update(self):
        self.counter += 1

    def elapsedTime(self):
        return time.time() - self.lastTime

    def reset(self):
        self.counter = 0
        self.lastTime = time.time()

    def rate(self):
        if self.counter > 0:
            return self.counter / self.elapsedTime()
        else:
            return 0.


class ImageStandardMean:
    def __init__(self):
        self.__mean = None  # Image mean
        self.__images = 0  # number of images

    def append(self, image):
        """Add a new image to the average"""
        if not isinstance(image, np.ndarray):
            raise ValueError("image has incorrect type: %s" % str(type(image)))

        # Update mean
        if self.__images > 0:
            if image.shape != self.shape:
                raise ValueError("image has incorrect shape: %s != %s" %
                                 (str(image.shape), str(self.shape)))

            self.__mean = (self.__mean * self.__images +
                           image) / (self.__images + 1)
            self.__images += 1
        else:
            self.__mean = image.astype('float64')
            self.__images = 1

    def clear(self):
        """Reset the mean"""
        self.__mean = None
        self.__images = 0

    @property
    def mean(self):
        """Return the mean"""
        return self.__mean

    @property
    def size(self):
        """Return the number of images in the average"""
        return self.__images

    @property
    def shape(self):
        """Return the shape of images in the average"""
        if self.size == 0:
            return ()
        else:
            return self.__mean.shape


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

            BOOL_ELEMENT(expected).key('runningAverage')
                .displayedName('Running Average')
                .description('Calculate running average (instead of '
                             'standard).')
                .assignmentOptional().defaultValue(True)
                .reconfigurable()
                .commit(),

            FLOAT_ELEMENT(expected).key('inFrameRate')
                .displayedName('Input Frame Rate')
                .description('The input frame rate.')
                .unit(Unit.HERTZ)
                .readOnly()
                .commit(),

            FLOAT_ELEMENT(expected).key('outFrameRate')
                .displayedName('Output Frame Rate')
                .description('The output frame rate.')
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
        self.imageStandardMean = ImageStandardMean()
        # Variables for frames per second computation
        self.frameRateIn = FrameRate()
        self.frameRateOut = FrameRate()

    def preReconfigure(self, incomingReconfiguration):
        if incomingReconfiguration.has('runningAverage'):
            # Reset averages
            self.resetAverage()

    def onData(self, data, metaData):
        """ This function will be called whenever a data token is availabe"""
        if self["state"] == State.PASSIVE:
            self.log.INFO("Start of Stream")
            self.updateState(State.ACTIVE)

        self.frameRateIn.update()
        if self.frameRateIn.elapsedTime() >= 1.0:
            fpsIn = self.frameRateIn.rate()
            self['inFrameRate'] = fpsIn
            self.log.DEBUG('Input rate %f Hz' % fpsIn)
            self.frameRateIn.reset()

        if data.has('data.image'):
            inputImage = data['data.image']
        elif data.has('image'):
            # To ensure backward compatibility
            # with older versions of cameras
            inputImage = data['image']
        else:
            self.log.DEBUG("Data contains no image at 'data.image'")
            return

        ts = Timestamp.fromHashAttributes(
            metaData.getAttributes('timestamp'))

        nImages = self['nImages']
        if nImages == 1:
            # No averaging needed
            h = Hash('data.image', inputImage)
            self.writeChannel('output', h, ts)
            return

        # Compute latency
        header = inputImage.getHeader()
        if header.has('creationTime'):
            self['latency'] = time.time() - header['creationTime']

        # Compute average
        pixels = inputImage.getData()
        runningAverage = self['runningAverage']
        h = Hash()
        if runningAverage:
            self.imageRunningMean.append(pixels, nImages)
            h.set('data.image',
                  ImageData(self.imageRunningMean.runningMean))
        else:
            self.imageStandardMean.append(pixels)
            if self.imageStandardMean.size >= nImages:
                h.set('data.image',
                      ImageData(self.imageStandardMean.mean))
                self.imageStandardMean.clear()

        if not h.empty():
            self.frameRateOut.update()
            if self.frameRateOut.elapsedTime() >= 1.0:
                fpsOut = self.frameRateOut.rate()
                self['outFrameRate'] = fpsOut
                self.log.DEBUG('Output rate %f Hz' % fpsOut)
                self.frameRateOut.reset()

            # For the averaged image, we use the timestamp of the
            # last image in the average
            self.writeChannel('output', h, ts)
            self.log.DEBUG('Averaged image sent to output channel')

    def onEndOfStream(self, inputChannel):
        self.log.INFO("End of Stream")
        self["inFrameRate"] = 0.
        self.updateState(State.PASSIVE)
        self.signalEndOfStream("output")

    def resetAverage(self):
        self.log.INFO('Reset image average and fps')
        self.imageRunningMean.clear()
        self.imageStandardMean.clear()
        self['inFrameRate'] = 0
        self['outFrameRate'] = 0
