#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on October 10, 2013
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################

from queue import Queue

import numpy as np

from karabo.bound import (
    DOUBLE_ELEMENT, IMAGEDATA_ELEMENT, NDARRAY_ELEMENT, NODE_ELEMENT,
    OUTPUT_CHANNEL, DaqDataType, Hash, ImageData, NoFsm, Schema, Types, Unit)
from processing_utils.rate_calculator import RateCalculator


class ImageProcOutputInterface(NoFsm):
    """Interface for processor output channels"""
    def __init__(self, configuration):
        # always call PythonDevice constructor first!
        super().__init__(configuration)

        self.shape = None
        self.kType = None

        # Output frame rate
        self.frame_rate_out = RateCalculator(refresh_interval=1.0)

    @staticmethod
    def expectedParameters(expected):
        outputData = Schema()
        (
            DOUBLE_ELEMENT(expected).key('outFrameRate')
            .displayedName('Output Frame Rate')
            .description('The output frame rate.')
            .unit(Unit.HERTZ)
            .readOnly()
            .commit(),

            OUTPUT_CHANNEL(expected).key("ppOutput")
            .displayedName("GUI/PP Output")
            .dataSchema(outputData)
            .commit(),

            # output channel for the DAQ
            OUTPUT_CHANNEL(expected).key("daqOutput")
            .displayedName("DAQ Output")
            .dataSchema(outputData)
            .commit(),
        )

    def updateOutputSchema(self, imageData):
        """Updates the schema of all the output channels"""
        if isinstance(imageData, list):
            # Internally, we deal with ndarrays.
            # Lists, coming from VECTOR_*_ELEMENTs, are therefore cast
            imageData = np.array(imageData)

        if isinstance(imageData, ImageData):
            pixels = imageData.getData()  # np.ndarray
            shape = pixels.shape
            kType = imageData.getType()
            updateSchemaHelper = self.updateImageSchemaHelper
        elif isinstance(imageData, np.ndarray):
            pixels = imageData
            shape = imageData.shape
            kType = Types.NUMPY
            updateSchemaHelper = self.updateNDArraySchemaHelper
        else:
            raise RuntimeError("Trying to update schema with invalid "
                               "imageData")

        if shape == self.shape and kType == self.kType:
            return  # schema unchanged no need to update

        self.shape = shape
        self.kType = kType
        self.daqShape = tuple(reversed(shape))

        newSchema = Schema()

        # update output Channel
        updateSchemaHelper(newSchema, "ppOutput", "Output", self.shape)

        # update DAQ output Channel
        updateSchemaHelper(newSchema, "daqOutput", "DAQ Output", self.daqShape)

        # update schema
        self.appendSchema(newSchema)

    def updateImageSchemaHelper(self, schema, outputNodeKey,
                                outputNodeName, shape):
        """Helper function - do not call it"""
        outputData = Schema()
        (
            NODE_ELEMENT(outputData).key("data")
            .displayedName("Data")
            .setDaqDataType(DaqDataType.TRAIN)
            .commit(),

            IMAGEDATA_ELEMENT(outputData).key("data.image")
            .displayedName("Image")
            .setDimensions(list(shape))
            .setType(Types.values[self.kType])
            .commit(),

            OUTPUT_CHANNEL(schema).key(outputNodeKey)
            .displayedName(outputNodeName)
            .dataSchema(outputData)
            .commit(),
        )

    def updateNDArraySchemaHelper(self, schema, outputNodeKey,
                                  outputNodeName, shape):
        """Helper function - do not call it"""
        outputData = Schema()
        (
            NODE_ELEMENT(outputData).key("data")
            .displayedName("Data")
            .setDaqDataType(DaqDataType.TRAIN)
            .commit(),

            NDARRAY_ELEMENT(outputData).key("data.image")
            .displayedName("Image")
            .shape(list(shape))
            .commit(),

            OUTPUT_CHANNEL(schema).key(outputNodeKey)
            .displayedName(outputNodeName)
            .dataSchema(outputData)
            .commit(),
        )

    def writeImageToOutputs(self, img, timestamp=None):
        """Writes the image to all the output channels"""
        if not isinstance(img, ImageData):
            raise RuntimeError(
                "Trying to feed writeImageToOutputs with invalid imageData")

        # write data to output channel
        self.writeChannel('ppOutput', Hash("data.image", img), timestamp)

        # swap image dimensions for DAQ compatibility
        daqImg = ImageData(img.getData().reshape(self.daqShape))

        # send data to DAQ output channel
        self.writeChannel('daqOutput', Hash("data.image", daqImg), timestamp)

    def writeNDArrayToOutputs(self, array, timestamp=None):
        """Write the array to all the output channels"""
        if not isinstance(array, np.ndarray):
            raise RuntimeError(
                "Trying to feed writeNDArrayToOutputs with invalid "
                "NDArray data")
        self.writeChannel('ppOutput', Hash("data.image", array), timestamp)
        daqArray = array.reshape(self.daqShape)
        self.writeChannel('daqOutput', Hash("data.image", daqArray), timestamp)

    def signalEndOfStreams(self):
        """Signals end-of-stream to all the output channels"""
        self.signalEndOfStream("ppOutput")
        self.signalEndOfStream("daqOutput")

    def refresh_frame_rate_out(self):
        self.frame_rate_out.update()
        fps_out = self.frame_rate_out.refresh()
        if fps_out:
            self['outFrameRate'] = fps_out
            self.log.DEBUG(f"Output rate {fps_out} Hz")


class ErrorCounter:
    def __init__(self, window_size=100, threshold=0.1, epsilon=0.01):
        self.queue = Queue(maxsize=window_size)
        self.count_error = 0
        self.last_warn_condition = False
        self.threshold = threshold
        self.epsilon = epsilon

    def append(self, error=False):
        if self.size == self.queue.maxsize:
            # queue full - pop first and update counters
            _error = self.queue.get(block=False)
            if _error and self.count_error > 0:
                self.count_error -= 1

        self.queue.put(error, block=False)
        if error:
            self.count_error += 1

    def clear(self):
        while self.size > 0:
            # pop all elements
            self.queue.get(block=False)
        self.count_error = 0
        self.last_warn_condition = False

    @property
    def size(self):
        return self.queue.qsize()

    @property
    def fraction(self):
        if self.size == 0:
            return 0.
        else:
            return self.count_error / self.size

    @property
    def warn(self):
        if self.last_warn_condition:
            # Go out of warn when fraction <= threshold - epsilon
            new_warn = self.fraction > self.threshold - self.epsilon
        else:
            # Enter warn when fraction >= threshold + epsilon
            new_warn = self.fraction >= self.threshold + self.epsilon

        self.last_warn_condition = new_warn
        return new_warn
