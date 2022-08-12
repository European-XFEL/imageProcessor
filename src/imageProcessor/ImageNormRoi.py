#############################################################################
# Author: dennis.goeries@xfel.eu
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

import numpy as np

from karabo.middlelayer import (
    AccessMode, Assignment, Configurable, DaqDataType, DaqPolicy, Device,
    Double, InputChannel, Node, OutputChannel, QuantityValue, Slot, State,
    Unit, VectorDouble, VectorInt32, VectorString, get_timestamp
)

from image_processing.image_processing import imageSumAlongY
from processing_utils.rate_calculator import RateCalculator


try:
    from .common import ErrorNode
    from ._version import version as deviceVersion
except ImportError:
    from imageProcessor.common import ErrorNode
    from imageProcessor._version import version as deviceVersion


class DataNode(Configurable):
    daqDataType = DaqDataType.TRAIN
    spectrum = VectorDouble(
        displayedName="Spectrum",
        accessMode=AccessMode.READONLY)


class ChannelNode(Configurable):
    data = Node(DataNode)


class ImageNormRoi(Device):
    # provide version for classVersion property
    __version__ = deviceVersion

    def __init__(self, configuration):
        super(ImageNormRoi, self).__init__(configuration)
        self.output.noInputShared = "drop"

    # TODO base class for MDL: interfaces, frameRate, errorCounter, input

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
        assignment=Assignment.MANDATORY)
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

            # Apply ROI and calculate integral
            x_roi = self.dataRoiPosition[0]
            y_roi = self.dataRoiPosition[1]
            x_norm_roi = self.normRoiPosition[0]
            y_norm_roi = self.normRoiPosition[1]
            width_roi = self.roiSize[0]
            height_roi = self.roiSize[1]
            if width_roi == 0 and height_roi == 0:
                # In case of [0, 0] no ROI is applied
                raise RuntimeError("ROI is [0, 0], please provide a valid one")
            else:
                # First the data_image
                data_image = image[y_roi:y_roi + height_roi,
                                   x_roi:x_roi + width_roi]
                norm_image = image[y_norm_roi:y_norm_roi + height_roi,
                                   x_norm_roi:x_norm_roi + width_roi]

            # Normalize the images
            data = data_image.astype('double')
            norm = norm_image.astype('double')
            difference = data - norm
            spectrum = imageSumAlongY(difference)
            self.spectrumIntegral = QuantityValue(spectrum.sum(),
                                                  timestamp=ts)

            self.errorCounter.update_count()  # success
            if self.status != "PROCESSING":
                self.status = "PROCESSING"
        except Exception as e:
            spectrum = np.full((1,), np.nan)
            self.spectrumIntegral = QuantityValue(np.NaN, timestamp=ts)
            if self.errorCounter.warnCondition == 0:
                # Only update if not yet in WARN
                msg = f"Exception while processing input image: {e}"
                self.status = msg
                self.log.ERROR(msg)
            self.errorCounter.update_count(True)

        # Write spectrum to output channel
        self.output.schema.data.spectrum = spectrum.tolist()

        await self.output.writeData(timestamp=ts)

    @input.endOfStream
    def input(self, name):
        self.frameRate = 0.
        if self.state != State.ON:
            self.state = State.ON

    roi_default = [0, 0]

    @VectorInt32(
        displayedName="ROI Size",
        description="The user-defined region of interest (ROI), "
                    "specified as [width_roi, height_roi]. ",
        minSize=2,
        maxSize=2,
        defaultValue=roi_default)
    def roiSize(self, value):
        if value is None:
            self.logger.error(f"Invalid initial ROI = {value.value}, reset to "
                              "default.")
            self.roiSize = [0, 0]
            return

        self.roiSize = value

    dataRoiPosition = VectorInt32(
        displayedName="Data Roi Position",
        description="The user-defined position of the data ROI of the "
                    "image [x, y]. Coordinates are taken top-left!",
        minSize=2,
        maxSize=2,
        defaultValue=roi_default)

    normRoiPosition = VectorInt32(
        displayedName="Norm Roi Position",
        description="The user-defined position of the ROI to normalize the "
                    "image [x, y]. Coordinates are taken top-left!",
        minSize=2,
        maxSize=2,
        defaultValue=roi_default)

    output = OutputChannel(
        ChannelNode,
        displayedName="Output")

    spectrumIntegral = Double(
        displayedName="Spectrum Integral",
        description="Integral of the spectrum, after applying ROI.",
        accessMode=AccessMode.READONLY)

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
