"""
Author: heisenb
Creation date: January, 2017, 05:21 PM
Copyright (c) European XFEL GmbH Hamburg. All rights reserved.
"""
import numpy as np
import time

from karabo.bound import (
    BOOL_ELEMENT, FLOAT_ELEMENT, ImageData, INPUT_CHANNEL, KARABO_CLASSINFO,
    OVERWRITE_ELEMENT, PythonDevice, Schema, SLOT_ELEMENT, State, Timestamp,
    UINT32_ELEMENT, Unit
)

from image_processing.image_running_mean import ImageRunningMean

from processing_utils.rate_calculator import RateCalculator

from .common import ImageProcOutputInterface


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
class ImageAverager(PythonDevice, ImageProcOutputInterface):

    @staticmethod
    def expectedParameters(expected):
        inputData = Schema()
        (
            OVERWRITE_ELEMENT(expected).key("state")
                .setNewOptions(State.PASSIVE, State.ACTIVE)
                .setNewDefaultValue(State.PASSIVE)
                .commit(),

            INPUT_CHANNEL(expected).key("input")
                .displayedName("Input")
                .dataSchema(inputData)
                .commit(),

            # Images should be dropped if processor is too slow
            OVERWRITE_ELEMENT(expected).key("input.onSlowness")
                .setNewDefaultValue("drop")
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
                .unit(Unit.SECOND)
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
        self.frame_rate_in = RateCalculator(refresh_interval=1.0)
        self.frame_rate_out = RateCalculator(refresh_interval=1.0)

    def preReconfigure(self, incomingReconfiguration):
        if incomingReconfiguration.has('runningAverage'):
            # Reset averages
            self.resetAverage()

    def onData(self, data, metaData):
        """ This function will be called whenever a data token is availabe"""
        firstImage = False
        if self.get("state") == State.PASSIVE:
            self.log.INFO("Start of Stream")
            self.updateState(State.ACTIVE)
            firstImage = True

        self.refreshFrameRateIn()

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
        pixels = inputImage.getData()
        bpp = inputImage.getBitsPerPixel()
        encoding = inputImage.getEncoding()

        dType = str(pixels.dtype)
        if firstImage:
            # Update schema
            self.updateOutputSchema(inputImage)

        # Compute latency
        header = inputImage.getHeader()
        if header.has('creationTime'):
            self['latency'] = time.time() - header['creationTime']

        # Compute average
        nImages = self['nImages']
        runningAverage = self['runningAverage']
        if nImages == 1:
            # No averaging needed
            self.writeImageToOutputs(inputImage, ts)
            self.refreshFrameRateOut()

        elif runningAverage:
            self.imageRunningMean.append(pixels, nImages)

            pixels = self.imageRunningMean.runningMean.astype(dType)
            imageData = ImageData(pixels, bitsPerPixel=bpp,
                                  encoding=encoding)

            self.writeImageToOutputs(imageData, ts)
            self.refreshFrameRateOut()

        else:
            self.imageStandardMean.append(pixels)
            if self.imageStandardMean.size >= nImages:
                pixels = self.imageStandardMean.mean.astype(dType)
                imageData = ImageData(pixels, bitsPerPixel=bpp,
                                      encoding=encoding)

                self.writeImageToOutputs(imageData, ts)
                self.refreshFrameRateOut()

                self.imageStandardMean.clear()

    def onEndOfStream(self, inputChannel):
        self.log.INFO("End of Stream")
        self.resetAverage()
        self.updateState(State.PASSIVE)
        self.signalEndOfStreams()

    def resetAverage(self):
        self.log.INFO('Reset image average and fps')
        self.imageRunningMean.clear()
        self.imageStandardMean.clear()
        self['inFrameRate'] = 0
        self['outFrameRate'] = 0

    def refreshFrameRateIn(self):
        self.frame_rate_in.update()
        fpsIn = self.frame_rate_in.refresh()
        if fpsIn:
            self['inFrameRate'] = fpsIn
            self.log.DEBUG('Input rate %f Hz' % fpsIn)

    def refreshFrameRateOut(self):
        self.frame_rate_out.update()
        fpsOut = self.frame_rate_out.refresh()
        if fpsOut:
            self['outFrameRate'] = fpsOut
            self.log.DEBUG('Output rate %f Hz' % fpsOut)
