"""
Author: heisenb
Creation date: January, 2017, 05:21 PM
Copyright (c) European XFEL GmbH Hamburg. All rights reserved.
"""
import numpy as np
import time

from karabo.bound import (
    BOOL_ELEMENT, DaqDataType, FLOAT_ELEMENT, Hash, ImageData,
    IMAGEDATA_ELEMENT, INPUT_CHANNEL, KARABO_CLASSINFO, NDARRAY_ELEMENT,
    NODE_ELEMENT, OUTPUT_CHANNEL, OVERWRITE_ELEMENT, PythonDevice, Schema,
    SLOT_ELEMENT, State, Timestamp, Types, UINT32_ELEMENT, Unit
)

from image_processing.image_running_mean import ImageRunningMean

from .common import FrameRate

DTYPE_TO_KTYPE = {
    'uint8': Types.UINT8,
    'int8': Types.INT8,
    'uint16': Types.UINT16,
    'int16': Types.INT16,
    'uint32': Types.UINT32,
    'int32': Types.INT32,
    'uint64': Types.UINT32,
    'float32': Types.FLOAT,
    'float': Types.DOUBLE,
    'double': Types.DOUBLE
}


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
        inputData = Schema()
        outputData = Schema()
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

            NODE_ELEMENT(outputData).key("data")
                .displayedName("Data")
                .setDaqDataType(DaqDataType.TRAIN)
                .commit(),

            IMAGEDATA_ELEMENT(outputData).key("data.image")
                .displayedName("Image")
                .commit(),

            OUTPUT_CHANNEL(expected).key("output")
                .displayedName("Output")
                .dataSchema(outputData)
                .commit(),

            # Second output channel for the DAQ
            OUTPUT_CHANNEL(expected).key("daqOutput")
                .displayedName("DAQ Output")
                .dataSchema(outputData)
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
        self.frameRateIn = FrameRate()
        self.frameRateOut = FrameRate()

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
        pixels = inputImage.getData()
        bpp = inputImage.getBitsPerPixel()
        encoding = inputImage.getEncoding()
        shape = inputImage.getDimensions()
        daqShape = tuple(reversed(shape))

        dType = str(pixels.dtype)
        if firstImage:
            # Update schema
            kType = DTYPE_TO_KTYPE.get(dType, None)
            self.updateOutputSchema(daqShape, encoding, kType)

        # Compute latency
        header = inputImage.getHeader()
        if header.has('creationTime'):
            self['latency'] = time.time() - header['creationTime']

        # Compute average
        nImages = self['nImages']
        runningAverage = self['runningAverage']
        outputHash = Hash()
        daqOutputHash = Hash()
        if nImages == 1:
            # No averaging needed
            outputHash.set('data.image', inputImage)

            daqPixels = pixels.reshape(daqShape)
            daqImageData = ImageData(daqPixels, bitsPerPixel=bpp,
                                     encoding=encoding)
            daqOutputHash.set('data.image', daqImageData)

        elif runningAverage:
            self.imageRunningMean.append(pixels, nImages)

            pixels = self.imageRunningMean.runningMean.astype(dType)
            imageData = ImageData(pixels, bitsPerPixel=bpp,
                                  encoding=encoding)
            outputHash.set('data.image', imageData)

            daqPixels = pixels.reshape(daqShape)
            daqImageData = ImageData(daqPixels, bitsPerPixel=bpp,
                                     encoding=encoding)
            daqOutputHash.set('data.image', daqImageData)

        else:
            self.imageStandardMean.append(pixels)
            if self.imageStandardMean.size >= nImages:
                pixels = self.imageStandardMean.mean.astype(dType)
                imageData = ImageData(pixels, bitsPerPixel=bpp,
                                      encoding=encoding)
                outputHash.set('data.image', imageData)

                daqPixels = pixels.reshape(daqShape)
                daqImageData = ImageData(daqPixels, bitsPerPixel=bpp,
                                         encoding=encoding)
                daqOutputHash.set('data.image', daqImageData)

                self.imageStandardMean.clear()

        if not outputHash.empty() and not daqOutputHash.empty():
            self.frameRateOut.update()
            if self.frameRateOut.elapsedTime() >= 1.0:
                fpsOut = self.frameRateOut.rate()
                self['outFrameRate'] = fpsOut
                self.log.DEBUG('Output rate %f Hz' % fpsOut)
                self.frameRateOut.reset()

            # For the averaged image, we use the timestamp of the
            # last image in the average
            self.writeChannel('output', outputHash, ts)
            self.writeChannel('daqOutput', daqOutputHash, ts)
            self.log.DEBUG('Averaged image sent to output channel')

    def onEndOfStream(self, inputChannel):
        self.log.INFO("End of Stream")
        self.resetAverage()
        self.updateState(State.PASSIVE)
        self.signalEndOfStream("output")

    def resetAverage(self):
        self.log.INFO('Reset image average and fps')
        self.imageRunningMean.clear()
        self.imageStandardMean.clear()
        self['inFrameRate'] = 0
        self['outFrameRate'] = 0

    def updateOutputSchema(self, daqShape, encoding, kType):
        newSchema = Schema()
        outputData = Schema()

        # Get device configuration before schema update
        try:
            outputHostname = self["daqOutput.hostname"]
        except AttributeError as e:
            # Configuration does not contain "daqOutput.hostname"
            outputHostname = None

        (
            NODE_ELEMENT(outputData).key("data")
                .displayedName("Data")
                .setDaqDataType(DaqDataType.TRAIN)
                .commit(),

            IMAGEDATA_ELEMENT(outputData).key("data.image")
                .displayedName("Image")
                .setDimensions(str(daqShape).strip("()"))
                .setEncoding(encoding)
                .commit(),

            # Set (overwrite) shape and dtype for internal NDArray element -
            # needed by DAQ
            NDARRAY_ELEMENT(outputData).key("data.image.pixels")
                .shape(str(daqShape).strip("()"))
                .dtype(kType)
                .commit(),

            # Set "maxSize" for vector properties - needed by DAQ
            outputData.setMaxSize("data.image.dims", len(daqShape)),
            outputData.setMaxSize("data.image.dimTypes", len(daqShape)),
            outputData.setMaxSize("data.image.roiOffsets", len(daqShape)),
            outputData.setMaxSize("data.image.binning", len(daqShape)),
            outputData.setMaxSize("data.image.pixels.shape", len(daqShape)),

            OUTPUT_CHANNEL(newSchema).key("daqOutput")
                .displayedName("DAQ Output")
                .dataSchema(outputData)
                .commit(),
        )

        self.updateSchema(newSchema)

        if outputHostname:
            # Restore configuration
            self.log.DEBUG("daqOutput.hostname: %s" % outputHostname)
            self.set("daqOutput.hostname", outputHostname)
