import time

from karabo.bound import (
    DaqDataType, Hash, ImageData, IMAGEDATA_ELEMENT, NODE_ELEMENT,
    NDARRAY_ELEMENT, NoFsm, OUTPUT_CHANNEL, Schema, Types
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
    'float': Types.DOUBLE,
    'double': Types.DOUBLE,
}


class FrameRate:
    def __init__(self, type='input', refresh_interval=1.0):
        self.counter = 0
        self.lastTime = time.time()
        self.type = type
        self.refresh_interval = refresh_interval

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

    def refresh(self):
        fps = None
        if self.elapsedTime() >= self.refresh_interval:
            fps = self.rate()
            self.reset()
        return fps


class ImageProcOutputInterface(NoFsm):
    def __init__(self, configuration):
        # always call PythonDevice constructor first!
        super(ImageProcOutputInterface, self).__init__(configuration)

        self.shape = None
        self.kType = None

    @staticmethod
    def expectedParameters(expected):
        outputData = Schema()
        (

            OUTPUT_CHANNEL(expected).key("output")
                .displayedName("Output")
                .dataSchema(outputData)
                .commit(),

            # output channel for the DAQ
            OUTPUT_CHANNEL(expected).key("daqOutput")
                .displayedName("DAQ Output")
                .dataSchema(outputData)
                .commit(),

        )

    def updateOutputSchema(self, imageData):
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
            outputHostname = self["output.hostname"]
        except AttributeError as e:
            # Configuration does not contain "output.hostname"
            outputHostname = None

        try:
            daqOutputHostname = self["daqOutput.hostname"]
        except AttributeError as e:
            # Configuration does not contain "output.hostname"
            daqOutputHostname = None

        newSchema = Schema()

        # update output Channel
        self.updateSchemaHelper(newSchema, "output", "Output", self.shape)

        # update DAQ output Channel
        self.updateSchemaHelper(newSchema, "daqOutput", "DAQ Output",
                                self.daqShape)

        # update schema
        self.updateSchema(newSchema)

        # Restore configuration
        if outputHostname:
            self.log.DEBUG("output.hostname: {}".format(outputHostname))
            self.set("output.hostname", outputHostname)
        if daqOutputHostname:
            self.log.DEBUG("daqOutput.hostname: {}".format(daqOutputHostname))
            self.set("daqOutput.hostname", daqOutputHostname)

    def updateSchemaHelper(self, schema, outputNodeKey, outputNodeName, shape):
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

    def writeOutputChannels(self, img, timestamp=None):

        if not isinstance(img, ImageData):
            raise RuntimeError(
                "Trying to feed writeOutputChannels with invalid "
                "imageData")

        # write data to output channel
        self.writeChannel('output', Hash("data.image", img), timestamp)

        # swap image dimensions for DAQ compatibility
        daqImg = ImageData(img.getData().reshape(self.daqShape))

        # send data to DAQ output channel
        self.writeChannel('daqOutput', Hash("data.image", daqImg), timestamp)
