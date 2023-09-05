#############################################################################
# Author: gabriele.giovanetti@xfel.eu
# Created on November 1st, 2018, 12:00 PM
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################

from image_processing.image_processing import (
    imageSumAlongX, imageSumAlongY, peakParametersEval)
from karabo.middlelayer import AccessMode, QuantityValue, UInt32, Unit

from ._version import version as deviceVersion
from .common_mdl import ImageProcessorBase


class BeamShapeCoarse(ImageProcessorBase):
    # provide version for classVersion property
    __version__ = deviceVersion

    x0 = UInt32(
        displayedName="Center X",
        description="X coordinate of the maximum intensity pixel.",
        unitSymbol=Unit.PIXEL,
        accessMode=AccessMode.READONLY
    )

    y0 = UInt32(
        displayedName="Center Y",
        description="Y coordinate of the maximum intensity pixel.",
        unitSymbol=Unit.PIXEL,
        accessMode=AccessMode.READONLY
    )

    fwhmX = UInt32(
        displayedName="FWHM X",
        description="Full Width at Half Maximum for X projection, "
                    "A.K.A. beam width.",
        unitSymbol=Unit.PIXEL,
        accessMode=AccessMode.READONLY
    )

    fwhmY = UInt32(
        displayedName="FWHM Y",
        description="Full Width at Half Maximum for Y projection, "
                    "A.K.A. beam height.",
        unitSymbol=Unit.PIXEL,
        accessMode=AccessMode.READONLY
    )

    # Overrides ImageProcessorBase.process_image
    async def process_image(self, image, ts):
        x_projection = imageSumAlongY(image)
        y_projection = imageSumAlongX(image)

        _, coord_x, fwhm_x = peakParametersEval(x_projection)
        _, coord_y, fwhm_y = peakParametersEval(y_projection)

        self.x0 = QuantityValue(coord_x, timestamp=ts, unit=Unit.PIXEL)
        self.y0 = QuantityValue(coord_y, timestamp=ts, unit=Unit.PIXEL)
        self.fwhmX = QuantityValue(fwhm_x, timestamp=ts, unit=Unit.PIXEL)
        self.fwhmY = QuantityValue(fwhm_y, timestamp=ts, unit=Unit.PIXEL)
