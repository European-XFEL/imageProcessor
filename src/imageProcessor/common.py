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
