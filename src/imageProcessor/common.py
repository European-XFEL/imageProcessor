from queue import Queue

from karabo.bound import (
    DaqDataType, Hash, ImageData, IMAGEDATA_ELEMENT, NODE_ELEMENT,
    NDARRAY_ELEMENT, NoFsm, OUTPUT_CHANNEL, Schema, Types
)

from karabo.middlelayer import (
    AccessLevel, AccessMode, Configurable, Double, UInt32, Unit
)

DTYPE_TO_KTYPE = {
    'uint8': Types.UINT8,
    'int8': Types.INT8,
    'uint16': Types.UINT16,
    'int16': Types.INT16,
    'uint32': Types.UINT32,
    'int32': Types.INT32,
    'uint64': Types.UINT64,
    'int64': Types.INT64,
    'float32': Types.FLOAT,
    'float64': Types.DOUBLE,
    'float': Types.DOUBLE,
    'double': Types.DOUBLE,
}


class ErrorNode(Configurable):
    count = UInt32(
        displayedName="Error Count",
        description="Number of errors.",
        unitSymbol=Unit.COUNT,
        accessMode=AccessMode.READONLY,
        defaultValue=0
    )

    windowSize = UInt32(
        displayedName="Window Size",
        description="Size of the sliding window for counting errors.",
        unitSymbol=Unit.NUMBER,
        accessMode=AccessMode.INITONLY,
        defaultValue=100,
        minInc=10,
        maxInc=6000
    )

    @Double(
        displayedName="Threshold",
        description="Threshold on the ratio errors/total counts, "
                    "for setting the alarmState.",
        unitSymbol=Unit.NUMBER,
        accessMode=AccessMode.RECONFIGURABLE,
        defaultValue=0.1,
        minInc=0.01,
        maxInc=1.
    )
    def threshold(self, value):
        self.threshold = value
        if hasattr(self, 'error_counter'):
            self.error_counter.threshold = value

    @Double(
        displayedName="Epsilon",
        description="The device will enter the alarm condition when "
                    "'fraction' exceeds threshold + epsilon, and will "
                    "leave it when fraction goes below threshold -"
                    " epsilon.",
        unitSymbol=Unit.NUMBER,
        accessMode=AccessMode.RECONFIGURABLE,
        requiredAccessLevel=AccessLevel.EXPERT,
        defaultValue=0.01,
        minInc=0.001,
        maxInc=1.
    )
    def epsilon(self, value):
        self.epsilon = value
        if hasattr(self, 'error_counter'):
            self.error_counter.epsilon = value

    fraction = Double(
        displayedName="Error Fraction",
        description="Fraction of errors in the specified window.",
        accessMode=AccessMode.READONLY,
        defaultValue=0
    )

    alarmCondition = UInt32(
        displayedName="Alarm Condition",
        description="True if the fraction of errors exceeds the "
                    "threshold.",
        accessMode=AccessMode.READONLY,
        defaultValue=0,
        alarmHigh=0,
        alarmNeedsAck_alarmHigh=False
    )

    def __init__(self, configuration):
        # always call superclass constructor first!
        super(ErrorNode, self).__init__(configuration)

        self.error_counter = ErrorCounter(
            window_size=int(self.windowSize.value),
            threshold=float(self.threshold),
            epsilon=float(self.epsilon))

    def update_alarm(self, error=False):
        self.error_counter.append(error)

        if self.count != self.error_counter.count_error:
            # Update in device only if changed
            self.count = self.error_counter.count_error

        if self.fraction != self.error_counter.fraction:
            # Update in device only if changed
            self.fraction = self.error_counter.fraction

        if self.alarmCondition != self.error_counter.alarm:
            # Update in device only if changed
            self.alarmCondition = self.error_counter.alarm


class ImageProcOutputInterface(NoFsm):
    """Interface for processor output channels"""
    def __init__(self, configuration):
        # always call PythonDevice constructor first!
        super(ImageProcOutputInterface, self).__init__(configuration)

        self.shape = None
        self.kType = None

    @staticmethod
    def expectedParameters(expected):
        outputData = Schema()
        (

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
        if isinstance(imageData, ImageData):
            pixels = imageData.getData()  # np.ndarray
            shape = pixels.shape
            kType = DTYPE_TO_KTYPE[pixels.dtype.name]
        else:
            raise RuntimeError("Trying to update schema with invalid "
                               "imageData")

        if shape == self.shape and kType == self.kType:
            return  # schema unchanged no need to update

        self.shape = shape
        self.kType = kType
        self.daqShape = tuple(reversed(shape))

        # Get device configuration before schema update
        try:
            outputHostname = self["ppOutput.hostname"]
        except AttributeError as e:
            # Configuration does not contain "ppOutput.hostname"
            outputHostname = None

        try:
            daqOutputHostname = self["daqOutput.hostname"]
        except AttributeError as e:
            # Configuration does not contain "daqOutput.hostname"
            daqOutputHostname = None

        newSchema = Schema()

        # update output Channel
        self.updateSchemaHelper(newSchema, "ppOutput", "Output", self.shape)

        # update DAQ output Channel
        self.updateSchemaHelper(newSchema, "daqOutput", "DAQ Output",
                                self.daqShape)

        # update schema
        self.updateSchema(newSchema)

        # Restore configuration
        if outputHostname:
            self.log.DEBUG("ppOutput.hostname: {}".format(outputHostname))
            self.set("ppOutput.hostname", outputHostname)
        if daqOutputHostname:
            self.log.DEBUG("daqOutput.hostname: {}".format(daqOutputHostname))
            self.set("daqOutput.hostname", daqOutputHostname)

    def updateSchemaHelper(self, schema, outputNodeKey, outputNodeName, shape):
        """Helper function - do not call it"""
        outputData = Schema()
        (
            NODE_ELEMENT(outputData).key("data")
            .displayedName("Data")
            .setDaqDataType(DaqDataType.TRAIN)
            .commit(),

            IMAGEDATA_ELEMENT(outputData).key("data.image")
            .displayedName("Image")
            .setDimensions(str(shape).strip("()"))
            .commit(),

            # Set (overwrite) shape and dtype for internal NDArray element -
            NDARRAY_ELEMENT(outputData).key("data.image.pixels")
            .shape(list(shape))
            .dtype(self.kType)
            .commit(),

            # Set "maxSize" for vector properties
            outputData.setMaxSize("data.image.dims", len(shape)),
            outputData.setMaxSize("data.image.dimTypes", len(shape)),
            outputData.setMaxSize("data.image.roiOffsets", len(shape)),
            outputData.setMaxSize("data.image.binning", len(shape)),
            outputData.setMaxSize("data.image.pixels.shape", len(shape)),

            OUTPUT_CHANNEL(schema).key(outputNodeKey)
            .displayedName(outputNodeName)
            .dataSchema(outputData)
            .commit(),
        )

    def writeImageToOutputs(self, img, timestamp=None):
        """Writes the image to all the output channels"""
        if not isinstance(img, ImageData):
            raise RuntimeError(
                "Trying to feed writeImageToOutputs with invalid "
                "imageData")

        # write data to output channel
        self.writeChannel('ppOutput', Hash("data.image", img), timestamp)

        # swap image dimensions for DAQ compatibility
        daqImg = ImageData(img.getData().reshape(self.daqShape))

        # send data to DAQ output channel
        self.writeChannel('daqOutput', Hash("data.image", daqImg), timestamp)

    def signalEndOfStreams(self):
        """Signals end-of-stream to all the output channels"""
        self.signalEndOfStream("ppOutput")
        self.signalEndOfStream("daqOutput")


class ErrorCounter:
    def __init__(self, window_size=100, threshold=0.1, epsilon=0.01):
        self.queue = Queue(maxsize=window_size)
        self.count_error = 0
        self.last_alarm_condition = False
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
        self.last_alarm_condition = False

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
    def alarm(self):
        if self.last_alarm_condition:
            # Go out of alarm when fraction <= threshold - epsilon
            new_alarm = self.fraction > self.threshold - self.epsilon
        else:
            # Enter alarm when fraction >= threshold + epsilon
            new_alarm = self.fraction >= self.threshold + self.epsilon

        self.last_alarm_condition = new_alarm
        return new_alarm
