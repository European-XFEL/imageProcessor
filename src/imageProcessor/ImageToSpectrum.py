#############################################################################
# Author: andrea.parenti@xfel.eu
# Created on June 22, 2018, 12:29 PM
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

from asyncio import coroutine
import numpy as np

from karabo.middlelayer import (
    AccessMode, Assignment, Configurable, DaqDataType, DaqPolicy, Device,
    Double, get_timestamp, InputChannel, Node, OutputChannel, QuantityValue,
    State, Type, VectorDouble, VectorInt32, VectorString
)

from image_processing.image_processing import imageSumAlongY


class DataNode(Configurable):
    daqDataType = DaqDataType.TRAIN
    spectrum = VectorDouble(
        displayedName="Spectrum",
        accessMode=AccessMode.READONLY
    )


class ChannelNode(Configurable):
    data = Node(DataNode)


class ImageToSpectrum(Device):
    def __init__(self, configuration):
        super(ImageToSpectrum, self).__init__(configuration)
        self.output.noInputShared = "drop"

    interfaces = VectorString(
        displayedName="Interfaces",
        defaultValue=["Processor"],
        accessMode=AccessMode.READONLY,
        daqPolicy=DaqPolicy.OMIT
    )

    @InputChannel(
        raw=True,
        displayedName="Input",
        accessMode=AccessMode.INITONLY,
        assignment=Assignment.MANDATORY
    )
    @coroutine
    def input(self, data, meta):
        if self.state != State.PROCESSING:
            self.state = State.PROCESSING

        ts = get_timestamp(meta.timestamp.timestamp)

        try:
            img_raw = data["data.image.pixels"]
            dtype = Type.types[img_raw["type"]].numpy
            shape = img_raw["shape"]
            # Convert bare Hash to NDArray
            image = np.frombuffer(img_raw["data"], dtype=dtype).reshape(shape)
            imageHeight = shape[0]
            imageWidth = shape[1]

            lowX = np.maximum(self.roi[0], 0)
            highX = np.minimum(self.roi[1], imageWidth)
            lowY = np.maximum(self.roi[2], 0)
            highY = np.minimum(self.roi[3], imageHeight)

            # Apply ROI
            if lowX == 0 and highX == 0 and lowY == 0 and highY == 0:
                # In case of [0, 0, 0 , 0] no ROI is applied
                image_data = image
            else:
                image_data = image[lowY:highY, lowX:highX]
            # Calculate spectrum
            spectrum = imageSumAlongY(image_data)
        except Exception as e:
            self.logger.error("Invalid image received: {}".format(e))
            return

        try:
            #Calculate integral
            self.spectrumIntegral = QuantityValue(spectrum.sum(),
                                                  timestamp=ts)
        except Exception as e:
            self.logger.error("Caught exception in 'input': {}".format(e))
            self.spectrumIntegral = QuantityValue(np.NaN, timestamp=ts)
            return

        # Write spectrum to output channel
        self.output.schema.data.spectrum = spectrum.astype('double').tolist()

        yield from self.output.writeData(timestamp=ts)

    @input.endOfStream
    def input(self, name):
        self.state = State.ON
        # TODO: send EOS to output (not possible in 2.2.4 yet)

    roiDefault = [0, 0, 0, 0]

    @VectorInt32(
        displayedName="ROI",
        description="The user-defined region of interest (ROI), "
                    "specified as [lowX, highX, lowY, highY]. "
                    "[0, 0, 0, 0] will be interpreted as 'whole range'.",
        minSize=4,
        maxSize=4,
        defaultValue=roiDefault,
    )
    def roi(self, value):
        if self.validRoi(value):
            self.roi = value
        elif self.roi.value is None:
            self.logger.error("Invalid initial ROI = {}, reset to "
                              "default.".format(value.value))
            self.roi = self.roiDefault
        else:
            self.logger.error("Invalid ROI: Cannot apply changes")

    output = OutputChannel(
        ChannelNode,
        displayedName="Output"
    )

    spectrumIntegral = Double(
        displayedName="Spectrum Integral",
        description="Integral of the spectrum, after applying ROI.",
        accessMode=AccessMode.READONLY,
    )

    def validRoi(self, roi):
        if any([roi[0] < 0, roi[1] < roi[0], roi[2] < 0, roi[3] < roi[2]]):
            return False
        return True

    @coroutine
    def onInitialization(self):
        """ This method will be called when the device starts.
        """
        self.state = State.ON
