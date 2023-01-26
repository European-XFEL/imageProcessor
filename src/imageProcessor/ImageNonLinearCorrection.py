#############################################################################
# Author: parenti
# Created on Jan 26th, 2023,  4:53 PM
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

import numpy as np

from karabo.middlelayer import (
    AccessMode, Assignment, Configurable, Device, Double, Image, InputChannel,
    Node, OutputChannel, State, Unit)


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
    frameRate = Double(
        displayedName="Input Frame Rate",
        description="Rate of processed images.",
        unitSymbol=Unit.HERTZ,
        accessMode=AccessMode.READONLY,
        defaultValue=0.
    )

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
            pass  # XXX do something
        except Exception:
            pass

    @input.endOfStream
    def input(self, name):
        self.frameRate = 0.
        if self.state != State.ON:
            self.state = State.ON

    output = OutputChannel(
        outputSchema(),
        displayedName="Output")
