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


def output_schema(shape=(0, 0), dtype=np.uint16):
    """Helper function to create the schema of the output channel

    :param shape: the shape of the image
    :param dtype: the dtype of the image
    :return: the output node
    """
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
        displayedName="Processing Rate",
        description="Rate of the image processing.",
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
            d_type = image.dtype

            if self.state != State.PROCESSING:
                # Set output schema
                schema = output_schema(image.shape, image.dtype)
                await self.setOutputSchema("output", schema)

                if d_type.kind in ('u', 'i'):
                    # For integer-type images we might need to clip the output
                    self.is_integer = True
                    self.a_min = np.iinfo(d_type).min
                    self.a_max = np.iinfo(d_type).max
                else:
                    self.is_integer = False
                    self.a_min = None
                    self.a_max = None

                self.state = State.PROCESSING

            self.frame_rate.update()
            fps = self.frame_rate.refresh()
            if fps:
                self.frameRate = fps

            if self.enable:
                baseline = max(  # estimate the baseline
                    2 * image.sum(axis=0).min() / image.shape[0],
                    2 * image.sum(axis=1).min() / image.shape[1],
                    0.02 * image.max())
                b = self.bParameter.value
                if self.autoScale.value:
                    # Scale factor to have image_out.max() == image.max()
                    a = image.max() ** (1.0 - b)
                else:
                    a = self.aParameter.value

                image_out = image.astype(float)  # convert to float
                image_out[image > baseline] = a * np.power(
                    image[image > baseline], b)  # reshape peak region
                if self.is_integer:  # clip the image
                    image_out = image_out.clip(self.a_min, self.a_max)
                if image_out.dtype == d_type:  # same dtype
                    self.output.schema.data.image = image_out
                else:  # cast to the orginal dtype
                    self.output.schema.data.image = image_out.astype(d_type)

            else:  # correction is disabled
                self.output.schema.data.image = image

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

    enable = Bool(
        displayedName="Enable Correction",
        description="Enable the non-linear correction.",
        defaultValue=True,
    )

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
        output_schema(),  # initial schema
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
