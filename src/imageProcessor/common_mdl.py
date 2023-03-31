#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on October 10, 2013
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################

from karabo.middlelayer import (
    AccessLevel, AccessMode, Configurable, Double, UInt32, Unit
)

try:
    from .common import ErrorCounter
except ImportError:
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
