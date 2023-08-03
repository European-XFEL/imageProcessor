#############################################################################
# Author: parenti
# Created on Jan 26th, 2023,  4:53 PM
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################

import numpy as np

from karabo.middlelayer import (
    Bool, Configurable, Double, Image, Node, OutputChannel, State)

try:
    from ._version import version as deviceVersion
    from .common_mdl import ImageProcessorBase
except ImportError:
    from imageProcessor._version import version as deviceVersion
    from imageProcessor.common_mdl import ImageProcessorBase


def create_output_schema(shape=(0, 0), dtype=np.uint16):
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


class ImageNonLinearCorrection(ImageProcessorBase):
    # provide version for classVersion property
    __version__ = deviceVersion

    # Overrides ImageProcessorBase.process_image
    async def process_image(self, image, ts):
        d_type = image.dtype

        if self.state != State.PROCESSING:
            if self.shape != image.shape or self.d_type != image.dtype:
                # Set output schema
                schema = create_output_schema(image.shape, image.dtype)
                await self.setOutputSchema("output", schema)
                self.shape = image.shape
                self.d_type = image.dtype

            if d_type.kind in ('u', 'i'):
                # For integer-type images clip the output
                self.is_integer = True
                self.a_min = np.iinfo(d_type).min
                self.a_max = np.iinfo(d_type).max
            else:
                self.is_integer = False
                self.a_min = None
                self.a_max = None

        if self.correctionEnabled:
            baseline = max(  # estimate the baseline
                2 * image.sum(axis=0).min() / image.shape[0],
                2 * image.sum(axis=1).min() / image.shape[1],
                0.02 * image.max())
            b = self.constB.value
            if self.autoScale.value:
                # Scale factor to have image_out.max() == image.max()
                a = (image.max() - baseline) ** (1.0 - b)
            else:
                a = self.constA.value

            image_out = image.astype(float)  # convert to float
            image_out[image > baseline] = baseline + a * np.power(
                image[image > baseline] - baseline, b)  # reshape peak
            if self.is_integer:  # clip the image
                image_out = image_out.clip(self.a_min, self.a_max)
            if image_out.dtype == d_type:  # same dtype
                self.output.schema.data.image = image_out
            else:  # cast to the orginal dtype
                self.output.schema.data.image = image_out.astype(d_type)

        else:  # correction is disabled
            self.output.schema.data.image = image

        await self.output.writeData(timestamp=ts)

    correctionEnabled = Bool(
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

    constA = Double(
        displayedName="a",
        description="The value for the constant 'a'. The output px values "
                    "will be: px_out = a * np.power(px_in, b). "
                    "This parameter has no effect if you select 'Auto-Scale'.",
        defaultValue=1.,
        minExc=0.,
    )

    constB = Double(
        displayedName="b",
        description="The value for the constant 'b'.The output px values "
                    "will be: px_out = a * np.power(px_in, b).",
        defaultValue=2.37,
        minInc=0.,
    )

    output = OutputChannel(
        create_output_schema(),  # initial schema
        displayedName="Output")

    async def onInitialization(self):
        """ This method will be called when the device starts."""
        await super().onInitialization()

        self.shape = (0, 0)
        self.d_type = np.uint16
