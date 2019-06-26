"""
Author: heisenb
Creation date: January, 2017, 05:21 PM
Copyright (c) European XFEL GmbH Hamburg. All rights reserved.
"""
import numpy as np

from karabo.bound import (
    BOOL_ELEMENT, DOUBLE_ELEMENT, ImageData, KARABO_CLASSINFO, SLOT_ELEMENT,
    State, STRING_ELEMENT, Timestamp, UINT32_ELEMENT, Unit
)

from image_processing.image_running_mean import ImageRunningMean

from processing_utils.rate_calculator import RateCalculator

try:
    from .common import ImageProcOutputInterface
    from .ImageProcessorBase import ImageProcessorBase
except ImportError:
    from imageProcessor.common import ImageProcOutputInterface
    from imageProcessor.ImageProcessorBase import ImageProcessorBase


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


@KARABO_CLASSINFO('ImageAverager', '2.4')
class ImageAverager(ImageProcessorBase, ImageProcOutputInterface):

    @staticmethod
    def expectedParameters(expected):
        (
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

            DOUBLE_ELEMENT(expected).key('outFrameRate')
            .displayedName('Output Frame Rate')
            .description('The output frame rate.')
            .unit(Unit.HERTZ)
            .readOnly()
            .commit(),
        )

    def __init__(self, configuration):
        # always call superclass constructor first!
        super(ImageAverager, self).__init__(configuration)

        # Get an instance of the mean calculator
        self.image_running_mean = ImageRunningMean()
        self.image_exp_running_mean = ImageExponentialRunnningAverage()
        self.image_standard_mean = ImageStandardMean()

        # Variables for frames per second computation
        self.frame_rate_in = RateCalculator(refresh_interval=1.0)
        self.frame_rate_out = RateCalculator(refresh_interval=1.0)

        # Register channel callback
        self.KARABO_ON_DATA('input', self.onData)
        self.KARABO_ON_EOS('input', self.onEndOfStream)

        # Register additional slot
        self.KARABO_SLOT(self.resetAverage)

    def preReconfigure(self, incomingReconfiguration):
        if incomingReconfiguration.has('runningAverage') or \
                incomingReconfiguration.has('runningAvgMethod'):
            # Reset averages
            self.resetAverage()

    def onData(self, data, metaData):
        """ This function will be called whenever a data token is availabe"""
        first_image = False
        if self['state'] == State.ON:
            self.log.INFO("Start of Stream")
            self.updateState(State.PROCESSING)
            first_image = True

        self.refresh_frame_rate_in()

        try:
            if data.has('data.image'):
                image_data = data['data.image']
            elif data.has('image'):
                # To ensure backward compatibility
                # with older versions of cameras
                image_data = data['image']
            else:
                raise RuntimeError("data does not contain any image")

            ts = Timestamp.fromHashAttributes(
                metaData.getAttributes('timestamp'))

            if first_image:
                # Update schema
                self.updateOutputSchema(image_data)

            self.process_image(image_data, ts)  # Process image

        except Exception as e:
            msg = "Exception caught in onData: {}".format(e)
            self.update_alarm(error=True, msg=msg)
            return

    def onEndOfStream(self, inputChannel):
        self.log.INFO("onEndOfStream called")
        self['inFrameRate'] = 0.
        self['outFrameRate'] = 0.
        # Signals end of stream
        self.signalEndOfStreams()
        self.updateState(State.ON)
        self['status'] = 'ON'

    def refresh_frame_rate_out(self):
        self.frame_rate_out.update()
        fps_out = self.frame_rate_out.refresh()
        if fps_out:
            self['outFrameRate'] = fps_out
            self.log.DEBUG("Output rate {} Hz".format(fps_out))

    def process_image(self, input_image, ts):
        try:
            pixels = input_image.getData()
            bpp = input_image.getBitsPerPixel()
            encoding = input_image.getEncoding()

            d_type = str(pixels.dtype)

            # Compute average
            n_images = self['nImages']
            running_average = self['runningAverage']
            if n_images == 1:
                # No averaging needed
                self.writeImageToOutputs(input_image, ts)
                self.update_alarm()  # Success
                self.refresh_frame_rate_out()
                return

            elif running_average:
                if self['runningAvgMethod'] == 'ExactRunningAverage':
                    self.image_running_mean.append(pixels, n_images)
                    pixels = self.image_running_mean.runningMean.astype(d_type)
                elif self['runningAvgMethod'] == 'ExponentialRunningAverage':
                    self.image_exp_running_mean.append(pixels, n_images)
                    pixels = self.image_exp_running_mean.mean.astype(d_type)
                image_data = ImageData(pixels, bitsPerPixel=bpp,
                                       encoding=encoding)

                self.writeImageToOutputs(image_data, ts)
                self.update_alarm()  # Success
                self.refresh_frame_rate_out()
                return

            else:
                self.image_standard_mean.append(pixels)
                if self.image_standard_mean.size >= n_images:
                    pixels = self.image_standard_mean.mean.astype(d_type)
                    image_data = ImageData(pixels, bitsPerPixel=bpp,
                                           encoding=encoding)

                    self.writeImageToOutputs(image_data, ts)
                    self.update_alarm()  # Success
                    self.refresh_frame_rate_out()

                    self.image_standard_mean.clear()
                    return

        except Exception as e:
            msg = "Exception caught in process_image: {}".format(e)
            self.update_alarm(error=True, msg=msg)

    ##############################################
    #   Implementation of Slots                  #
    ##############################################

    def resetAverage(self):
        self.log.INFO('Reset image average and fps')
        self.image_running_mean.clear()
        self.image_exp_running_mean.clear()
        self.image_standard_mean.clear()
        self['inFrameRate'] = 0
        self['outFrameRate'] = 0
