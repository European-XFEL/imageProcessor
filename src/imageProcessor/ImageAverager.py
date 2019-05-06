"""
Author: heisenb
Creation date: January, 2017, 05:21 PM
Copyright (c) European XFEL GmbH Hamburg. All rights reserved.
"""
import numpy as np
import time

from karabo.bound import (
    BOOL_ELEMENT, FLOAT_ELEMENT, ImageData, INPUT_CHANNEL, KARABO_CLASSINFO,
    OVERWRITE_ELEMENT, PythonDevice, Schema, SLOT_ELEMENT, State,
    STRING_ELEMENT, Timestamp, UINT32_ELEMENT, Unit, VECTOR_STRING_ELEMENT
)

from image_processing.image_running_mean import ImageRunningMean

from processing_utils.rate_calculator import RateCalculator

from .common import ImageProcOutputInterface


class ImageExponentialRunnningAverage:
    """Simple, fast and efficient running average method, widely used in
    machine learning to track running statistics. It does not need to store
    a 100000 image ringbuffer: the running average is held by a single numpy
    array with the same size as the image and updated as the weighted average
    of the previous state and the new frame according to:
    ```
    AVG_new = w*IMG_new + (1-w)*AVG_old
    ```
    The number of averaged frames sets the decay rate and can be changed
    without clearing the buffer, i.e. you can start with a faster decay and
    slow it down after initial convergence. The weighted average is stored as
    a float64 array and must be converted back to the image type.
    """

    def __init__(self):
        self.__nimages = 1.0
        self.__mean = None

    @property
    def __tau(self):
        """The decay rate is the inverse of the number of frames."""
        return 1.0 / self.__nimages

    def clear(self):
        """Reset the mean"""
        self.__mean = None

    def append(self, image, n_images):
        """Add a new image to the average"""
        # Check for correct type and input values
        if not isinstance(image, np.ndarray):
            raise ValueError("Image has incorrect type: %s" % str(type(image)))
        if n_images <= 0:
            raise ValueError("The averager's smoothing rate must be positive "
                             "instead of %f." % n_images)

        # We assign the smoothing coefficient
        self.__nimages = n_images

        if self.__mean is None:
            # If running average is empty, we explicitly assign fp64
            self.__mean = image.astype(np.float64)
        else:
            # If it's already running, just update the state
            self.__mean = self.__tau * image + (1.0 - self.__tau) * self.__mean

    @property
    def mean(self):
        """Returns the current mean"""
        return self.__mean

    @property
    def size(self):
        """Return the inverse decay rate"""
        return self.__nimages

    @property
    def shape(self):
        if self.__mean is None:
            return ()
        else:
            return self.__mean.shape


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
                .setNewOptions(State.ON, State.PROCESSING)
                .setNewDefaultValue(State.ON)
                .commit(),

            VECTOR_STRING_ELEMENT(expected).key("interfaces")
                .displayedName("Interfaces")
                .readOnly()
                .initialValue(["Processor"])
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

            STRING_ELEMENT(expected).key('runningAvgMethod')
                .displayedName('Running average Method')
                .description('The algorithm used for calculating the '
                             'running average.')
                .options("ExactRunningAverage,ExponentialRunningAverage")
                .assignmentOptional()
                .defaultValue('ExactRunningAverage')
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
        self.imageExpRunningMean = ImageExponentialRunnningAverage()
        self.imageStandardMean = ImageStandardMean()
        # Variables for frames per second computation
        self.frame_rate_in = RateCalculator(refresh_interval=1.0)
        self.frame_rate_out = RateCalculator(refresh_interval=1.0)

    def preReconfigure(self, incomingReconfiguration):
        if incomingReconfiguration.has('runningAverage') or \
                incomingReconfiguration.has('runningAvgMethod'):
            # Reset averages
            self.resetAverage()

    def onData(self, data, metaData):
        """ This function will be called whenever a data token is available"""
        firstImage = False
        if self.get("state") == State.ON:
            self.log.INFO("Start of Stream")
            self.updateState(State.PROCESSING)
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
            if self['runningAvgMethod'] == 'ExactRunningAverage':
                self.imageRunningMean.append(pixels, nImages)
                pixels = self.imageRunningMean.runningMean.astype(dType)
            elif self['runningAvgMethod'] == 'ExponentialRunningAverage':
                self.imageExpRunningMean.append(pixels, nImages)
                pixels = self.imageExpRunningMean.mean.astype(dType)

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
        self.updateState(State.ON)
        self.signalEndOfStreams()

    def resetAverage(self):
        self.log.INFO('Reset image average and fps')
        self.imageRunningMean.clear()
        self.imageExpRunningMean.clear()
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
