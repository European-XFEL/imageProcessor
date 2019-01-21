#############################################################################
# Author: dennis.goeries@xfel.eu
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
        accessMode=AccessMode.READONLY)


class ChannelNode(Configurable):
    data = Node(DataNode)


class ImageNormRoi(Device):
    def __init__(self, configuration):
        super(ImageNormRoi, self).__init__(configuration)
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
        assignment=Assignment.MANDATORY)
    @coroutine
    def input(self, data, meta):
        if self.state != State.ACTIVE:
            self.state = State.ACTIVE

        image = data.data.image.pixels.value
        ts = get_timestamp(meta.timestamp.timestamp)

        try:
            # Apply ROI and calculate integral
            x_roi = self.dataRoiPosition[0]
            y_roi = self.dataRoiPosition[1]
            x_norm_roi = self.normRoiPosition[0]
            y_norm_roi = self.normRoiPosition[1]
            width_roi = self.roiSize[0]
            height_roi = self.roiSize[1]
            if width_roi == 0 and height_roi == 0:
                # In case of [0, 0] no ROI is applied
                self.spectrumIntegral = np.NaN
                self.logger.info("Please provide valid ROI")
                return
            else:
                # First the data_image
                data_image = image[y_roi:y_roi + height_roi,
                                   x_roi:x_roi + width_roi]
                norm_image = image[y_norm_roi:y_norm_roi + height_roi,
                                   x_norm_roi:x_norm_roi + width_roi]

            # Normalize the images
            data = data_image.astype('double')
            norm = norm_image.astype('double')
            difference = data - norm
            spectrum = imageSumAlongY(difference)
            self.spectrumIntegral = QuantityValue(spectrum.sum(), ts)
        except Exception as e:
            self.logger.error("Caught exception in 'input': {}".format(e))
            self.spectrumIntegral = QuantityValue(np.NaN, ts)
            return

        # Write spectrum to output channel
        self.output.schema.data.spectrum = spectrum.tolist()

        yield from self.output.writeData(timestamp=ts)

    @input.endOfStream
    def input(self, name):
        self.state = State.PASSIVE

    roiDefault = [0, 0]

    @VectorInt32(
        displayedName="ROI Size",
        description="The user-defined region of interest (ROI), "
                    "specified as [width_roi, height_roi]. ",
        minSize=2,
        maxSize=2,
        defaultValue=roiDefault)
    def roiSize(self, value):
        if value is None:
            self.logger.error("Invalid initial ROI = {}, reset to "
                              "default.".format(value.value))
            self.roiSize = [0, 0]
            return

        self.roiSize = value

    dataRoiPosition = VectorInt32(
        displayedName="Data Roi Position",
        description="The user-defined position of the data ROI of the "
                    "image [x, y]. Coordinates are taken top-left!",
        minSize=2,
        maxSize=2,
        defaultValue=roiDefault)

    normRoiPosition = VectorInt32(
        displayedName="Norm Roi Position",
        description="The user-defined position of the ROI to normalize the "
                    "image [x, y]. Coordinates are taken top-left!",
        minSize=2,
        maxSize=2,
        defaultValue=roiDefault)

    output = OutputChannel(
        ChannelNode,
        displayedName="Output")

    spectrumIntegral = Double(
        displayedName="Spectrum Integral",
        description="Integral of the spectrum, after applying ROI.",
        accessMode=AccessMode.READONLY)

    @coroutine
    def onInitialization(self):
        """ This method will be called when the device starts.
        """
        self.state = State.PASSIVE
