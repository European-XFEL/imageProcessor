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
    State, VectorDouble, VectorInt32, VectorString
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
        raw=False,
        displayedName="Input",
        accessMode=AccessMode.INITONLY,
        assignment=Assignment.MANDATORY
    )
    @coroutine
    def input(self, data, meta):
        if self.state != State.ACTIVE:
            self.state = State.ACTIVE

        if hasattr(data, 'data.image'):
            image = getattr(data, 'data.image')
        elif hasattr(data, 'image'):
            # To ensure backward compatibility
            # with older versions of cameras
            image = getattr(data, 'image')
        else:
            self.logger.error("Data contains no image at 'data.image")
            return

        ts = get_timestamp(meta.timestamp.timestamp)

        try:
            # Calculate spectrum
            spectrum = imageSumAlongY(image.pixels.value)
        except Exception as e:
            self.logger.error("Invalid image received: {}".format(e))
            return

        try:
            # Apply ROI and calculate integral
            lowX = self.roi[0]
            highX = self.roi[1]
            if lowX == 0 and highX == 0:
                # In case of [0, 0] no ROI is applied
                cropSpectrum = spectrum
            else:
                cropSpectrum = spectrum[lowX:highX]
            self.spectrumIntegral = QuantityValue(cropSpectrum.sum(), ts)
        except Exception as e:
            self.logger.error("Caught exception in 'input': {}".format(e))
            self.spectrumIntegral = QuantityValue(np.NaN, ts)
            return

        # Write spectrum to output channel
        self.output.schema.data.spectrum = spectrum.astype('double').tolist()

        yield from self.output.writeData(timestamp=ts)

    @input.endOfStream
    def input(self, name):
        self.state = State.PASSIVE
        # TODO: send EOS to output (not possible in 2.2.4 yet)

    roiDefault = [0, 0]

    @VectorInt32(
        displayedName="ROI",
        description="The user-defined region of interest (ROI), "
                    "specified as [lowX, highX]. "
                    "[0, 0] will be interpreted as 'whole range'.",
        minSize=2,
        maxSize=2,
        defaultValue=roiDefault,
    )
    def roi(self, value):
        if self.validRoi(value):
            self.roi = value
        elif self.roi.value is None:
            self.logger.error("Invalid initial ROI = {}, reset to "
                              "default.".format(value.value))
            self.roi = self.roiDefault

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
        if roi[0] < 0 or roi[1] < roi[0]:
            return False
        return True

    @coroutine
    def onInitialization(self):
        """ This method will be called when the device starts.
        """
        self.state = State.PASSIVE
