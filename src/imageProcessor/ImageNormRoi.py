#############################################################################
# Author: dennis.goeries@xfel.eu
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################

import numpy as np

from image_processing.image_processing import imageSumAlongY
from karabo.middlelayer import (
    AccessMode, Configurable, DaqDataType, Double, Node, OutputChannel,
    QuantityValue, VectorDouble, VectorInt32)

from ._version import version as deviceVersion
from .common_mdl import ImageProcessorBase


class DataNode(Configurable):
    daqDataType = DaqDataType.TRAIN
    spectrum = VectorDouble(
        displayedName="Spectrum",
        accessMode=AccessMode.READONLY)


class ChannelNode(Configurable):
    data = Node(DataNode)


class ImageNormRoi(ImageProcessorBase):
    # provide version for classVersion property
    __version__ = deviceVersion

    def __init__(self, configuration):
        super().__init__(configuration)
        self.output.noInputShared = "drop"

    # Overrides ImageProcessorBase.process_image
    async def process_image(self, image, ts):
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
                raise RuntimeError("ROI is [0, 0], please provide a valid one")
            else:
                # First the data_image
                data_image = image[
                    y_roi:y_roi + height_roi, x_roi:x_roi + width_roi]
                norm_image = image[
                    y_norm_roi:y_norm_roi + height_roi,
                    x_norm_roi:x_norm_roi + width_roi]

            # Normalize the images
            data = data_image.astype('double')
            norm = norm_image.astype('double')
            difference = data - norm
            spectrum = imageSumAlongY(difference)
            self.spectrumIntegral = QuantityValue(
                spectrum.sum(), timestamp=ts)

        except Exception:
            spectrum = np.full((1,), np.nan)
            self.spectrumIntegral = QuantityValue(np.NaN, timestamp=ts)
            raise

        finally:
            # Write spectrum to output channel
            self.output.schema.data.spectrum = spectrum.tolist()

            await self.output.writeData(timestamp=ts)

    roi_default = [0, 0]

    @VectorInt32(
        displayedName="ROI Size",
        description="The user-defined region of interest (ROI), "
                    "specified as [width_roi, height_roi]. ",
        minSize=2,
        maxSize=2,
        defaultValue=roi_default)
    def roiSize(self, value):
        if value is None:
            self.logger.error(f"Invalid initial ROI = {value.value}, reset to "
                              "default.")
            self.roiSize = [0, 0]
            return

        self.roiSize = value

    dataRoiPosition = VectorInt32(
        displayedName="Data Roi Position",
        description="The user-defined position of the data ROI of the "
                    "image [x, y]. Coordinates are taken top-left!",
        minSize=2,
        maxSize=2,
        defaultValue=roi_default)

    normRoiPosition = VectorInt32(
        displayedName="Norm Roi Position",
        description="The user-defined position of the ROI to normalize the "
                    "image [x, y]. Coordinates are taken top-left!",
        minSize=2,
        maxSize=2,
        defaultValue=roi_default)

    output = OutputChannel(
        ChannelNode,
        displayedName="Output")

    spectrumIntegral = Double(
        displayedName="Spectrum Integral",
        description="Integral of the spectrum, after applying ROI.",
        accessMode=AccessMode.READONLY)
