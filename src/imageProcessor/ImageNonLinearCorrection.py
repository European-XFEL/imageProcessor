#############################################################################
# Author: parenti
# Created on Jan 26th, 2023,  4:53 PM
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

import numpy as np

from karabo.middlelayer import (
    AccessMode, Assignment, Bool, Configurable, DaqPolicy, Device, Double,
    Image, InputChannel, Node, OutputChannel, Slot, State, Unit, VectorString,
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
        displayedName="Frame Rate",
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
            baseline = 3 * max(
                image.sum(axis=0).min() / image.shape[0],
                image.sum(axis=1).min() / image.shape[1])

            if self.state != State.PROCESSING:
                # Set output schema
                schema = outputSchema(image.shape, image.dtype)
                await self.setOutputSchema("output", schema)

                dt = image.dtype
                self.dtype = dt
                if dt.kind in ('u', 'i'):
                    self.is_integer = True
                    self.a_min = np.iinfo(dt).min
                    self.a_max = np.iinfo(dt).max
                else:
                    self.is_integer = False

                self.state = State.PROCESSING

            self.frame_rate.update()
            fps = self.frame_rate.refresh()
            if fps:
                self.frameRate = fps

            b = self.bParameter.value
            if self.autoScale.value:
                # Scale factor to have image_out.max() == image_in.max()
                a = image.max() ** (1.0 - b)
            else:
                a = self.aParameter.value

            image_out = image.astype(float)  # copy
            image_out[image > baseline] = a * np.power(
                image[image > baseline], b)  # reshape peak region
            if self.is_integer:  # clip the image
                image_out = image_out.clip(self.a_min, self.a_max)
            if image_out.dtype != self.dtype:
                # cast to the orginal dtype
                self.output.schema.data.image = image_out.astype(self.dtype)
            else:
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

    autoScale = Bool(
        displayedName="Auto-Scale",
        description="Auto-scale the pixel values so that the output image "
                    "peak has the same heigth as the input.",
        defaultValue=True,
    )

    aParameter = Double(
        displayedName="a",
        description="The value for the constant 'a'. The output px values "
                    "will be: px_out = a * np.power(px_in, b). "
                    "This parameter has no effect if you select 'Auto-Scale'.",
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
