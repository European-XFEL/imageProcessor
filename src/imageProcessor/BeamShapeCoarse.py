#############################################################################
# Author: gabriele.giovanetti@xfel.eu
# Created on November 1st, 2018, 12:00 PM
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

from asyncio import coroutine

from karabo.middlelayer import (
    AccessMode, Assignment, Device, Double, get_timestamp, InputChannel,
    QuantityValue, Slot, State, UInt32, Unit
)

from image_processing.image_processing import (
    imageSumAlongX, imageSumAlongY, peakParametersEval
)

from DaqCompliancy.DaqCompliancy import DaqCompliant

from .common import FrameRate


class BeamShapeCoarse(DaqCompliant, Device):
    x0 = UInt32(
        displayedName="Center X",
        description="X coordinate of the maximum intensity pixel",
        unitSymbol=Unit.PIXEL,
        accessMode=AccessMode.READONLY
    )

    y0 = UInt32(
        displayedName="Center Y",
        description="Y coordinate of the maximum intensity pixel",
        unitSymbol=Unit.PIXEL,
        accessMode=AccessMode.READONLY
    )

    fwhmX = UInt32(
        displayedName="FWHM X",
        description="Full Widh at Half Maximum for X projection, "
                    "A.K.A. beam width",
        unitSymbol=Unit.PIXEL,
        accessMode=AccessMode.READONLY
    )

    fwhmY = UInt32(
        displayedName="FWHM Y",
        description="Full Widh at Half Maximum for Y projection, "
                    "A.K.A. beam height",
        unitSymbol=Unit.PIXEL,
        accessMode=AccessMode.READONLY
    )

    frameRate = Double(
        displayedName="Input Frame Rate",
        description="Rate of processed images",
        unitSymbol=Unit.HERTZ,
        accessMode=AccessMode.READONLY,
    )

    @InputChannel(
        raw=False,
        displayedName="Input",
        accessMode=AccessMode.INITONLY,
        assignment=Assignment.MANDATORY
    )
    @coroutine
    def input(self, data, meta):
        try:
            img_timestamp = get_timestamp(meta.timestamp.timestamp)

            img = data.data.image.pixels.value

            x_projection = imageSumAlongY(img)
            y_projection = imageSumAlongX(img)

            _, coord_x, fwhm_x = peakParametersEval(x_projection)
            _, coord_y, fwhm_y = peakParametersEval(y_projection)

            self.x0 = QuantityValue(coord_x, timestamp=img_timestamp)
            self.y0 = QuantityValue(coord_y, timestamp=img_timestamp)
            self.fwhmX = QuantityValue(fwhm_x, timestamp=img_timestamp)
            self.fwhmY = QuantityValue(fwhm_y, timestamp=img_timestamp)
            if self.state != State.ACTIVE:
                self.state = State.ACTIVE
            self.frame_rate.update()
            fps = self.frame_rate.refresh()
            if fps:
                self.frameRate = fps
        except Exception as e:
            if self.state != State.ERROR:
                self.state = State.ERROR
            msg = "Exception while processing input image: {}".format(e)
            if self.status != msg:
                self.status = msg

    @input.endOfStream
    def input(self, name):
        if self.state != State.PASSIVE:
            self.state = State.PASSIVE

    @coroutine
    def onInitialization(self):
        """ This method will be called when the device starts.
        """
        self.frame_rate = FrameRate(refresh_interval=1.0)

        self.state = State.PASSIVE

    @Slot(displayedName='Reset', allowedStates=[State.ERROR])
    def resetError(self):
        self.state = State.PASSIVE
