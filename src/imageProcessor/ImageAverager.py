"""
Author: heisenb
Creation date: January, 2017, 05:21 PM
Copyright (c) European XFEL GmbH Hamburg. All rights reserved.
"""
import numpy as np

from karabo.bound import (
    BOOL_ELEMENT, ImageData, KARABO_CLASSINFO, SLOT_ELEMENT, State,
    STRING_ELEMENT, Timestamp, UINT32_ELEMENT, Unit
)

from image_processing.image_exp_running_average import (
    ImageExponentialRunnningAverage
)
from image_processing.image_running_mean import ImageRunningMean
from image_processing.image_standard_mean import ImageStandardMean

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

            BOOL_ELEMENT(expected).key('convertToFloat')
            .displayedName('Convert to Float')
            .description('Use floating point pixel values for the '
                         'averaged image instead of the source type')
            .assignmentOptional().defaultValue(False)
            .expertAccess()
            .reconfigurable()
            .allowedStates(State.ON)
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
        )

    def __init__(self, configuration):
        # always call superclass constructor first!
        super().__init__(configuration)
        self.is_image_data = None
        self.is_ndarray = None

        # Get an instance of the mean calculator
        self.image_running_mean = ImageRunningMean()
        self.image_exp_running_mean = ImageExponentialRunnningAverage()
        self.image_standard_mean = ImageStandardMean()

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
                self.is_image_data = isinstance(image_data, ImageData)
                self.is_ndarray = isinstance(image_data, np.ndarray)

            if self.is_image_data:
                self.process_image(image_data, ts, first_image)
            elif self.is_ndarray:
                self.process_ndarray(image_data, ts, first_image)
            else:
                self.process_ndarray(np.array(image_data), ts, first_image)

        except Exception as e:
            msg = f"Exception caught in onData: {e}"
            self.update_count(error=True, status=msg)
            return

    def onEndOfStream(self, inputChannel):
        self.log.INFO("onEndOfStream called")
        self['inFrameRate'] = 0.
        self['outFrameRate'] = 0.
        # Signals end of stream
        self.signalEndOfStreams()
        self.updateState(State.ON)
        self['status'] = 'Idle'

    def process_image(self, input_image, ts, first_image):
        try:
            pixels = input_image.getData()
            in_dtype = pixels.dtype
            if self['convertToFloat']:
                out_dtype = np.float32
            else:
                out_dtype = in_dtype

            # Compute average
            n_images = self['nImages']
            running_average = self['runningAverage']
            if n_images == 1:
                # No averaging needed
                if in_dtype != out_dtype:
                    pixels = pixels.astype(out_dtype)
                    input_image.setData(pixels)
                self.write_image(input_image, ts, first_image)
                return

            elif running_average:
                if self['runningAvgMethod'] == 'ExactRunningAverage':
                    self.image_running_mean.append(pixels, n_images)
                    pixels = self.image_running_mean.runningMean
                elif self['runningAvgMethod'] == 'ExponentialRunningAverage':
                    self.image_exp_running_mean.append(pixels, n_images)
                    pixels = self.image_exp_running_mean.mean
                if pixels.dtype != out_dtype:
                    pixels = pixels.astype(out_dtype)
                input_image.setData(pixels)
                self.write_image(input_image, ts, first_image)
                return

            else:
                self.image_standard_mean.append(pixels)
                if self.image_standard_mean.size >= n_images:
                    pixels = self.image_standard_mean.mean
                    if pixels.dtype != out_dtype:
                        pixels = pixels.astype(out_dtype)
                    input_image.setData(pixels)
                    self.write_image(input_image, ts, first_image)

                    self.image_standard_mean.clear()
                    return

        except Exception as e:
            msg = f"Exception caught in process_image: {e}"
            self.update_count(error=True, status=msg)

    def write_image(self, image, ts, first_image):
        """This function will: 1. update the device schema (if needed);
        2. write the image to the output channels; 3. refresh the error count
        and frame rates."""

        if first_image:
            # Update schema
            self.updateOutputSchema(image)

        self.writeImageToOutputs(image, ts)
        self.update_count()  # Success
        self.refresh_frame_rate_out()

    def process_ndarray(self, array, ts, first_image):
        n_images = self['nImages']
        running_average = self['runningAverage']

        in_dtype = array.dtype
        if self['convertToFloat']:
            out_dtype = np.float32
        else:
            out_dtype = in_dtype

        try:
            if n_images == 1:
                pass  # No averaging needed

            elif running_average:
                if self['runningAvgMethod'] == 'ExactRunningAverage':
                    self.image_running_mean.append(array, n_images)
                    array = self.image_running_mean.runningMean
                elif self['runningAvgMethod'] == 'ExponentialRunningAverage':
                    self.image_exp_running_mean.append(array, n_images)
                    array = self.image_exp_running_mean.mean.astype

            else:
                self.image_standard_mean.append(array)
                if self.image_standard_mean.size >= n_images:
                    array = self.image_standard_mean.mean
                    self.image_standard_mean.clear()
        except Exception as e:
            msg = f"Exception caught in process_ndarray: {e}"
            self.update_count(error=True, status=msg)
        else:
            if array.dtype != out_dtype:
                array = array.astype(out_dtype)
            if first_image:
                # Update schema
                self.updateOutputSchema(array)

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
