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

from image_processing.image_exp_running_average import (
    ImageExponentialRunnningAverage
)
from image_processing.image_running_mean import ImageRunningMean
from image_processing.image_standard_mean import ImageStandardMean

from processing_utils.rate_calculator import RateCalculator

try:
    from .common import ImageProcOutputInterface
    from .ImageProcessorBase import ImageProcessorBase
    from ._version import version as deviceVersion
except ImportError:
    from imageProcessor.common import ImageProcOutputInterface
    from imageProcessor.ImageProcessorBase import ImageProcessorBase
    from imageProcessor._version import version as deviceVersion


@KARABO_CLASSINFO('ImageAverager', deviceVersion)
class ImageAverager(ImageProcessorBase, ImageProcOutputInterface):

    @staticmethod
    def expectedParameters(expected):
        (
            SLOT_ELEMENT(expected).key('resetAverage')
            .displayedName('Reset Average')
            .description('Reset averaged image.')
            .commit(),

            STRING_ELEMENT(expected).key("imagePath")
            .displayedName("Image Path")
            .description("The path within the channel, where the data is, such"
                         " as data.image, digitizer.channel_1_A.raw.samples")
            .assignmentOptional().defaultValue("data.image")
            .expertAccess()
            .init()
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
            .defaultValue('ExponentialRunningAverage')
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
        self.is_image_data = False

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
        # always call ImageProcessorBase preReconfigure first!
        super(ImageAverager, self).preReconfigure(incomingReconfiguration)

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
            image_path = self['imagePath']
            if data.has(image_path):
                image_data = data[image_path]
            else:
                raise RuntimeError("data does not contain any image")

            ts = Timestamp.fromHashAttributes(
                metaData.getAttributes('timestamp'))

            if first_image:
                # Update schema
                self.is_image_data = isinstance(image_data, ImageData)
                self.updateOutputSchema(image_data)

            if self.is_image_data:
                self.process_image(image_data, ts)
            else:
                self.process_ndarray(np.array(image_data), ts)

        except Exception as e:
            msg = "Exception caught in onData: {}".format(e)
            self.update_count(error=True, msg=msg)
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
                self.update_count()  # Success
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
                self.update_count()  # Success
                self.refresh_frame_rate_out()
                return

            else:
                self.image_standard_mean.append(pixels)
                if self.image_standard_mean.size >= n_images:
                    pixels = self.image_standard_mean.mean.astype(d_type)
                    image_data = ImageData(pixels, bitsPerPixel=bpp,
                                           encoding=encoding)

                    self.writeImageToOutputs(image_data, ts)
                    self.update_count()  # Success
                    self.refresh_frame_rate_out()

                    self.image_standard_mean.clear()
                    return

        except Exception as e:
            msg = "Exception caught in process_image: {}".format(e)
            self.update_count(error=True, msg=msg)

    def process_ndarray(self, array, ts):
        n_images = self['nImages']
        running_average = self['runningAverage']
        try:
            if n_images == 1:
                pass  # No averaging needed

            elif running_average:
                if self['runningAvgMethod'] == 'ExactRunningAverage':
                    self.image_running_mean.append(array, n_images)
                    array = self.image_running_mean.runningMean.astype(np.float64)  # noqa
                elif self['runningAvgMethod'] == 'ExponentialRunningAverage':
                    self.image_exp_running_mean.append(array, n_images)
                    array = self.image_exp_running_mean.mean.astype(np.float64)

            else:
                self.image_standard_mean.append(array)
                if self.image_standard_mean.size >= n_images:
                    array = self.image_standard_mean.mean.astype(np.float64)
                    self.image_standard_mean.clear()
        except Exception as e:
            msg = "Exception caught in process_ndarray: {}".format(e)
            self.update_count(error=True, msg=msg)
        else:
            self.writeNDArrayToOutputs(array, ts)
            self.refresh_frame_rate_out()
            self.update_count()  # Success

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
