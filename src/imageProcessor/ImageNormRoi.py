#############################################################################
# Author: dennis.goeries@xfel.eu
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

from asyncio import coroutine
import numpy as np

from karabo.middlelayer import (
    AccessMode, Assignment, Configurable, DaqDataType, Device, Double,
    InputChannel, Node, OutputChannel, State, VectorDouble, VectorInt32
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


class ImageNormRoi(Device):
    def __init__(self, configuration):
        super(ImageNormRoi, self).__init__(configuration)
        self.output.noInputShared = "drop"

    @InputChannel(
        raw=False,
        displayedName="Input",
        accessMode=AccessMode.INITONLY,
        assignment=Assignment.MANDATORY)
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

        try:
            # Calculate spectrum
            spectrum = imageSumAlongY(image.pixels.value)
        except Exception as e:
            self.logger.error("Invalid image received: {}".format(e))
            return

        try:
            # Apply ROI and calculate integral
            width_roi = self.roiSize[0]
            height_roi = self.roiSize[1]
            if width_roi == 0 and height_roi == 0:
                # In case of [0, 0] no ROI is applied
                cropSpectrum = spectrum
            else:
                cropSpectrum = spectrum[width_roi:height_roi]
            self.spectrumIntegral = cropSpectrum.sum()
        except Exception as e:
            self.logger.error("Caught exception in 'input': {}".format(e))
            self.spectrumIntegral = np.NaN
            return

        # Write spectrum to output channel
        self.output.schema.data.spectrum = spectrum.astype('double').tolist()
        yield from self.output.writeData()

    @input.endOfStream
    def input(self, name):
        self.state = State.PASSIVE

    roiDefault = [0, 0]

    @VectorInt32(
        displayedName="ROI Size",
        description="The user-defined region of interest (ROI), "
                    "specified as [width_roi, height_roi]. "
                    "[0, 0] will be interpreted as 'whole range'.",
        minSize=2,
        maxSize=2,
        defaultValue=roiDefault)
    def roi(self, value):
        if self.validRoi(value):
            self.roiSize = value
        elif self.roiSize.value is None:
            self.logger.error("Invalid initial ROI = {}, reset to "
                              "default.".format(value.value))
            self.roiSize = self.roiSizeDefault

    output = OutputChannel(
        ChannelNode,
        displayedName="Output")

    spectrumIntegral = Double(
        displayedName="Spectrum Integral",
        description="Integral of the spectrum, after applying ROI.",
        accessMode=AccessMode.READONLY)

    def validRoi(self, roi):
        if roi[0] < 0 or roi[1] < roi[0]:
            return False
        return True

    @coroutine
    def onInitialization(self):
        """ This method will be called when the device starts.
        """
        self.state = State.PASSIVE
