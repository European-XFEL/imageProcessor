#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on October 10, 2013
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################

from karabo.middlelayer import (
    AccessLevel, AccessMode, Assignment, Configurable, DaqPolicy, Device,
    Double, InputChannel, Node, Slot, State, String, UInt32, Unit,
    VectorString, get_timestamp)
from processing_utils.rate_calculator import RateCalculator

try:
    from ._version import version as deviceVersion
    from .common import ErrorCounter
except ImportError:
    from imageProcessor._version import version as deviceVersion
    from imageProcessor.common import ErrorCounter


class ErrorNode(Configurable):
    count = UInt32(
        displayedName="Error Count",
        description="Number of errors.",
        unitSymbol=Unit.COUNT,
        accessMode=AccessMode.READONLY,
        defaultValue=0
    )

    windowSize = UInt32(
        displayedName="Window Size",
        description="Size of the sliding window for counting errors.",
        unitSymbol=Unit.NUMBER,
        accessMode=AccessMode.INITONLY,
        defaultValue=100,
        minInc=10,
        maxInc=6000
    )

    @Double(
        displayedName="Threshold",
        description="Threshold on the ratio errors/total counts, "
                    "for setting the warn condition.",
        unitSymbol=Unit.NUMBER,
        accessMode=AccessMode.RECONFIGURABLE,
        defaultValue=0.1,
        minInc=0.01,
        maxInc=1.
    )
    def threshold(self, value):
        self.threshold = value
        if hasattr(self, 'error_counter'):
            self.error_counter.threshold = value
            self.evaluate_warn()

    @Double(
        displayedName="Epsilon",
        description="The device will enter the warn condition when "
                    "'fraction' exceeds threshold + epsilon, and will "
                    "leave it when fraction goes below threshold -"
                    " epsilon.",
        unitSymbol=Unit.NUMBER,
        accessMode=AccessMode.RECONFIGURABLE,
        requiredAccessLevel=AccessLevel.EXPERT,
        defaultValue=0.01,
        minInc=0.001,
        maxInc=1.
    )
    def epsilon(self, value):
        self.epsilon = value
        if hasattr(self, 'error_counter'):
            self.error_counter.epsilon = value
            self.evaluate_warn()

    fraction = Double(
        displayedName="Error Fraction",
        description="Fraction of errors in the specified window.",
        accessMode=AccessMode.READONLY,
        defaultValue=0
    )

    warnCondition = UInt32(
        displayedName="Warn Condition",
        description="True if the fraction of errors exceeds the "
                    "threshold.",
        accessMode=AccessMode.READONLY,
        defaultValue=0,
        warnHigh=0,
        alarmNeedsAck_warnHigh=False
    )

    def __init__(self, configuration):
        # always call superclass constructor first!
        super().__init__(configuration)

        self.error_counter = ErrorCounter(
            window_size=int(self.windowSize.value),
            threshold=float(self.threshold),
            epsilon=float(self.epsilon))

    def update_count(self, error=False):
        self.error_counter.append(error)
        self.evaluate_warn()

    def evaluate_warn(self):
        if self.count != self.error_counter.count_error:
            # Update in device only if changed
            self.count = self.error_counter.count_error

        if self.fraction != self.error_counter.fraction:
            # Update in device only if changed
            self.fraction = self.error_counter.fraction

        if self.warnCondition != self.error_counter.warn:
            # Update in device only if changed
            self.warnCondition = self.error_counter.warn


class ImageProcessorBase(Device):
    # provide version for classVersion property
    __version__ = deviceVersion

    imagePath = String(
        displayedName="Image Path",
        description="Input image path.",
        defaultValue="data.image",
        requiredAccessLevel=AccessLevel.EXPERT,
        accessMode=AccessMode.INITONLY,
    )

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

    errorCounter = Node(
        ErrorNode,
        displayedName="Error Count",
        description="This node provides a count of the processing errors, "
                    "a warn condition if the error fraction exceeds some "
                    "settable threshold, ad more.")

    @InputChannel(
        raw=False,
        displayedName="Input",
        accessMode=AccessMode.INITONLY,
        assignment=Assignment.MANDATORY)
    async def input(self, data, meta):
        try:
            image = data
            for key in self.imagePath.value.split("."):
                image = getattr(image, key)
            image = image.pixels.value

            self.frame_rate.update()
            fps = self.frame_rate.refresh()
            if fps:
                self.frameRate = fps

            ts = get_timestamp(meta.timestamp.timestamp)
            await self.process_image(image, ts)

            self.errorCounter.update_count()  # success

            if self.state != State.PROCESSING:
                self.state = State.PROCESSING
                self.status = "PROCESSING"

        except Exception as e:
            if self.errorCounter.warnCondition == 0:
                # Only update if not yet in WARN
                msg = f"Exception while processing input image: {e}"
                self.status = msg
                self.log.ERROR(msg)
            self.errorCounter.update_count(True)

    async def process_image(self, image, ts):
        raise NotImplementedError(
            "This function must be overridden in the derived class.")

    @input.endOfStream
    def input(self, name):
        self.frameRate = 0.
        if self.state != State.ON:
            self.state = State.ON
            self.status = "IDLE"

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
        self.status = "IDLE"
        self.state = State.ON
