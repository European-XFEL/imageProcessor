#############################################################################
# Author: parenti
# Created on Jan 26th, 2023,  4:53 PM
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

import numpy as np

from karabo.middlelayer import (
    AccessMode, Assignment, Configurable, DaqPolicy, Device, Double, Image,
    InputChannel, Node, OutputChannel, Slot, State, Unit, VectorString,
    get_timestamp)

from processing_utils.rate_calculator import RateCalculator

try:
    from .common_mdl import ErrorNode
    from ._version import version as deviceVersion
except ImportError:
    from imageProcessor.common_mdl import ErrorNode
    from imageProcessor._version import version as deviceVersion


def outputSchema(shape=(0, 0), dtype=np.uint16):
    class DataNode(Configurable):
        image = Image(
            shape=shape,
            dtype=dtype,
            displayedName="Image")

    class OutputNode(Configurable):
        data = Node(DataNode)

    return OutputNode


class ImageNonLinearCorrection(Device):
    # provide version for classVersion property
    __version__ = deviceVersion

    interfaces = VectorString(
        displayedName="Interfaces",
        defaultValue=["Processor"],
        accessMode=AccessMode.READONLY,
        daqPolicy=DaqPolicy.OMIT
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
        try:
            ts = get_timestamp(meta.timestamp.timestamp)
            image = data.data.image.pixels.value

            if self.state != State.PROCESSING:
                # Set output schema
                schema = outputSchema(image.shape, image.dtype)
                await self.setOutputSchema("output", schema)

                self.state = State.PROCESSING

            self.frame_rate.update()
            fps = self.frame_rate.refresh()
            if fps:
                self.frameRate = fps

            a = self.aParameter.value
            b = self.bParameter.value
            image_out = a * np.power(image, b)
            self.output.schema.data.image = image_out
            await self.output.writeData(timestamp=ts)

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
        self.status = "IDLE"
        self.frameRate = 0.
        if self.state != State.ON:
            self.state = State.ON

    aParameter = Double(
        displayedName="a",
        description="The value for the constant 'a'. The output px values "
                    "will be: px_out = a * np.power(px_in, b).",
        defaultValue=1.,
        minExc=0.,
    )

    bParameter = Double(
        displayedName="b",
        description="The value for the constant 'b'.The output px values "
                    "will be: px_out = a * np.power(px_in, b).",
        defaultValue=2.37,
        minInc=0.,
    )

    output = OutputChannel(
        outputSchema(),
        displayedName="Output")

    @Slot(displayedName='Reset', description="Reset error count.")
    async def resetError(self):
        self.errorCounter.error_counter.clear()
        self.errorCounter.evaluate_warn()
        if self.state != State.ON:
            self.state = State.ON

    async def onInitialization(self):
        """ This method will be called when the device starts."""
        self.frame_rate = RateCalculator(refresh_interval=1.0)
        self.state = State.ON
        self.status = "IDLE"
