#############################################################################
# Author: andrea.parenti@xfel.eu
# Created on June 22, 2018, 12:29 PM
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################

import numpy as np

from image_processing.image_processing import imageSumAlongX, imageSumAlongY
from karabo.middlelayer import (
    AccessMode, Bool, Configurable, DaqDataType, Double, Node, OutputChannel,
    QuantityValue, VectorDouble, VectorInt32)

from ._version import version as deviceVersion
from .common_mdl import ImageProcessorBase


class DataNode(Configurable):
    daqDataType = DaqDataType.TRAIN
    spectrum = VectorDouble(
        displayedName="Spectrum",
        accessMode=AccessMode.READONLY
    )


class ChannelNode(Configurable):
    data = Node(DataNode)


class ImageToSpectrum(ImageProcessorBase):
    # provide version for classVersion property
    __version__ = deviceVersion

    def __init__(self, configuration):
        super().__init__(configuration)
        self.output.noInputShared = "drop"
        if self.xIntegral:
            self.calculate_spectrum = imageSumAlongX
        else:
            self.calculate_spectrum = imageSumAlongY

    async def process_image(self, image, ts):
        try:
            image_height = image.shape[0]
            image_width = image.shape[1]

            low_x = np.maximum(self.roi[0], 0)
            high_x = np.minimum(self.roi[1], image_width)
            low_y = np.maximum(self.roi[2], 0)
            high_y = np.minimum(self.roi[3], image_height)

            # Apply ROI
            if low_x == 0 and high_x == 0 and low_y == 0 and high_y == 0:
                # In case of [0, 0, 0, 0] no ROI is applied
                cropped_image = image
            else:
                cropped_image = image[int(low_y):int(high_y),
                                      int(low_x):int(high_x)]

            # Calculate spectrum
            spectrum = self.calculate_spectrum(cropped_image)

            # Calculate integral
            self.spectrumIntegral = QuantityValue(spectrum.sum(),
                                                  timestamp=ts)

        except Exception:
            spectrum = np.full((1,), np.nan)
            self.spectrumIntegral = QuantityValue(np.NaN, timestamp=ts)
            raise

        finally:
            # Write spectrum to output channel
            self.output.schema.data.spectrum = spectrum.astype(
                'double').tolist()

            await self.output.writeData(timestamp=ts)

    roi_default = [0, 0, 0, 0]

    @VectorInt32(
        displayedName="ROI",
        description="The user-defined region of interest (ROI), "
                    "specified as [lowX, highX, lowY, highY]. "
                    "[0, 0, 0, 0] will be interpreted as 'whole range'.",
        minSize=4,
        maxSize=4,
        defaultValue=roi_default,
    )
    def roi(self, value):
        if self.valid_roi(value):
            self.roi = value
        elif self.roi.value is None:
            self.logger.error(f"Invalid initial ROI = {value.value}, reset to "
                              "default.")
            self.roi = self.roi_default
        else:
            self.logger.error("Invalid ROI: Cannot apply changes")

    output = OutputChannel(
        ChannelNode,
        displayedName="Output"
    )

    xIntegral = Bool(
        displayedName="Integrate in X",
        description="Integrate the image in X direction. By default integral "
                    "is done over Y.",
        accessMode=AccessMode.INITONLY,
        defaultValue=False
    )

    spectrumIntegral = Double(
        displayedName="Spectrum Integral",
        description="Integral of the spectrum, after applying ROI.",
        accessMode=AccessMode.READONLY,
    )

    def valid_roi(self, roi):
        if any([roi[0] < 0, roi[1] < roi[0], roi[2] < 0, roi[3] < roi[2]]):
            return False
        return True
