#############################################################################
# Author: gabriele.giovanetti@xfel.eu
# Created on November 1st, 2018, 12:00 PM
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

from karabo.middlelayer import (
    AccessMode, Assignment, DaqPolicy, Device, Double, get_timestamp,
    InputChannel, Node, QuantityValue, Slot, State, UInt32, Unit, VectorString
)

from image_processing.image_processing import (
    imageSumAlongX, imageSumAlongY, peakParametersEval
)
from processing_utils.rate_calculator import RateCalculator

try:
    from .common_mdl import ErrorNode
    from ._version import version as deviceVersion
except ImportError:
    from imageProcessor.common_mdl import ErrorNode
    from imageProcessor._version import version as deviceVersion


class BeamShapeCoarse(Device):

    # provide version for classVersion property
    __version__ = deviceVersion

    # TODO base class for MDL: interfaces, frameRate, errorCounter, input

    interfaces = VectorString(
        displayedName="Interfaces",
        defaultValue=["Processor"],
        accessMode=AccessMode.READONLY,
        daqPolicy=DaqPolicy.OMIT
    )

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

    frameRate = Double(
        displayedName="Input Frame Rate",
        description="Rate of processed images.",
        unitSymbol=Unit.HERTZ,
        accessMode=AccessMode.READONLY,
        defaultValue=0.
    )

    errorCounter = Node(ErrorNode)

    @InputChannel(
        raw=False,
        displayedName="Input",
        accessMode=AccessMode.INITONLY,
        assignment=Assignment.MANDATORY
    )
    async def input(self, data, meta):
        if self.state != State.PROCESSING:
            self.state = State.PROCESSING

        try:
            ts = get_timestamp(meta.timestamp.timestamp)
            image = data.data.image.pixels.value

            self.frame_rate.update()
            fps = self.frame_rate.refresh()
            if fps:
                self.frameRate = fps

            x_projection = imageSumAlongY(image)
            y_projection = imageSumAlongX(image)

            _, coord_x, fwhm_x = peakParametersEval(x_projection)
            _, coord_y, fwhm_y = peakParametersEval(y_projection)

            self.x0 = QuantityValue(coord_x, timestamp=ts)
            self.y0 = QuantityValue(coord_y, timestamp=ts)
            self.fwhmX = QuantityValue(fwhm_x, timestamp=ts)
            self.fwhmY = QuantityValue(fwhm_y, timestamp=ts)

            self.errorCounter.update_count()  # success
            if self.status != "PROCESSING":
                self.status = "PROCESSING"
        except Exception as e:
            if self.errorCounter.warnCondition == 0:
                msg = f"Exception while processing input image: {e}"
                # Only update if not yet in WARN
                self.status = msg
                self.log.ERROR(msg)
            self.errorCounter.update_count(True)

    @input.endOfStream
    def input(self, name):
        self.frameRate = 0.
        if self.state != State.ON:
            self.state = State.ON

    @Slot(displayedName='Reset', description="Reset error count.")
    async def resetError(self):
        self.errorCounter.error_counter.clear()
        self.errorCounter.evaluate_warn()
        if self.state != State.ON:
            self.state = State.ON

    async def onInitialization(self):
        """ This method will be called when the device starts.
        """
        self.frame_rate = RateCalculator(refresh_interval=1.0)
        self.state = State.ON
