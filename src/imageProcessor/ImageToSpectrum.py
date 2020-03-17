#############################################################################
# Author: andrea.parenti@xfel.eu
# Created on June 22, 2018, 12:29 PM
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

import numpy as np

from karabo.middlelayer import (
    AccessMode, Assignment, Bool, Configurable, DaqDataType, DaqPolicy, Device,
    Double, get_timestamp, InputChannel, Node, OutputChannel, QuantityValue,
    Slot, State, Type, Unit, VectorDouble, VectorInt32, VectorString
)

from image_processing.image_processing import imageSumAlongX, imageSumAlongY

from processing_utils.rate_calculator import RateCalculator

try:
    from .common import ErrorNode
except ImportError:
    from imageProcessor.common import ErrorNode


class DataNode(Configurable):
    daqDataType = DaqDataType.TRAIN
    spectrum = VectorDouble(
        displayedName="Spectrum",
        accessMode=AccessMode.READONLY
    )


class ChannelNode(Configurable):
    data = Node(DataNode)


class ImageToSpectrum(Device):
    def __init__(self, configuration):
        super(ImageToSpectrum, self).__init__(configuration)
        self.output.noInputShared = "drop"
        if self.xIntegral:
            self.calculate_spectrum = imageSumAlongX
        else:
            self.calculate_spectrum = imageSumAlongY

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
        raw=True,
        displayedName="Input",
        accessMode=AccessMode.INITONLY,
        assignment=Assignment.MANDATORY
    )
    async def input(self, data, meta):
        if self.state != State.PROCESSING:
            self.state = State.PROCESSING

        try:
            ts = get_timestamp(meta.timestamp.timestamp)
            img_raw = data["data.image.pixels"]
            img_type = img_raw["type"]
            dtype = np.dtype(Type.types[img_type].numpy)
            shape = img_raw["shape"]

            # Convert bare Hash to NDArray
            image = np.frombuffer(img_raw["data"], dtype=dtype).reshape(shape)
            image_height = shape[0]
            image_width = shape[1]

            self.frame_rate.update()
            fps = self.frame_rate.refresh()
            if fps:
                self.frameRate = fps

            low_x = np.maximum(self.roi[0], 0)
            high_x = np.minimum(self.roi[1], image_width)
            low_y = np.maximum(self.roi[2], 0)
            high_y = np.minimum(self.roi[3], image_height)

            # Apply ROI
            if low_x == 0 and high_x == 0 and low_y == 0 and high_y == 0:
                # In case of [0, 0, 0 , 0] no ROI is applied
                cropped_image = image
            else:
                cropped_image = image[low_y:high_y, low_x:high_x]

            # Calculate spectrum
            spectrum = self.calculate_spectrum(cropped_image)

            # Calculate integral
            self.spectrumIntegral = QuantityValue(spectrum.sum(),
                                                  timestamp=ts)

            self.errorCounter.update_count()  # success
            if self.status != "PROCESSING":
                self.status = "PROCESSING"
        except Exception as e:
            spectrum = np.full((1,), np.nan)
            self.spectrumIntegral = QuantityValue(np.NaN, timestamp=ts)
            msg = "Exception while processing input image: {}".format(e)
            if self.errorCounter.warnCondition == 0:
                # Only update if not yet in WARN
                self.status = msg
                self.log.ERROR(msg)
            self.errorCounter.update_count(True)

        # Write spectrum to output channel
        self.output.schema.data.spectrum = spectrum.astype('double').tolist()

        await self.output.writeData(timestamp=ts)

    @input.endOfStream
    def input(self, name):
        self.frameRate = 0.
        if self.state != State.ON:
            self.state = State.ON
        # TODO: send EOS to output (not possible in 2.2.4 yet)

    roi_default = [0, 0, 0, 0]

    @VectorInt32(
        displayedName="ROI",
        description="The user-defined region of interest (ROI), "
                    "specified as [lowX, highX, lowY, highY]. "
                    "[0, 0, 0, 0] will be interpreted as 'whole range'.",
        minSize=4,
        maxSize=4,
        defaultValue=roi_default,
    )
    def roi(self, value):
        if self.valid_roi(value):
            self.roi = value
        elif self.roi.value is None:
            self.logger.error("Invalid initial ROI = {}, reset to "
                              "default.".format(value.value))
            self.roi = self.roi_default
        else:
            self.logger.error("Invalid ROI: Cannot apply changes")

    output = OutputChannel(
        ChannelNode,
        displayedName="Output"
    )

    xIntegral = Bool(
        displayedName="Integrate in X",
        description="Integrate the image in X direction. By default integral "
                    "is done over Y.",
        accessMode=AccessMode.INITONLY,
        defaultValue=False
    )

    spectrumIntegral = Double(
        displayedName="Spectrum Integral",
        description="Integral of the spectrum, after applying ROI.",
        accessMode=AccessMode.READONLY,
    )

    @Slot(displayedName='Reset',  description="Reset error count.")
    async def resetError(self):
        self.errorCounter.error_counter.clear()
        self.errorCounter.evaluate_warn()
        if self.state != State.ON:
            self.state = State.ON

    def valid_roi(self, roi):
        if any([roi[0] < 0, roi[1] < roi[0], roi[2] < 0, roi[3] < roi[2]]):
            return False
        return True

    async def onInitialization(self):
        """ This method will be called when the device starts.
        """
        self.frame_rate = RateCalculator(refresh_interval=1.0)
        self.state = State.ON
