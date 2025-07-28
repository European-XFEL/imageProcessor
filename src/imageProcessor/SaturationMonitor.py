#############################################################################
# Author: <astrid.muennich@xfel.eu>
# Created on March 28, 2024
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################

import numpy as np

from karabo.bound import (
    BOOL_ELEMENT, FLOAT_ELEMENT, KARABO_CLASSINFO, NODE_ELEMENT,
    UINT64_ELEMENT, Hash, ImageData, State, Timestamp)

from ._version import version as deviceVersion
from .common import ImageProcOutputInterface
from .ImageProcessorBase import ImageProcessorBase


@KARABO_CLASSINFO("SaturationMonitor", deviceVersion)
class SaturationMonitor(ImageProcessorBase, ImageProcOutputInterface):
    """ This device should help identify if a detector is exposed to too much
    light.
    Based on the given threshold in units of the image the number of
    pixels above those thresholds is determined. For multi-frame data the max
    value for each pixel is considered.
    A boolean indicates if the number of pixel above threshold is too high."""

    @staticmethod
    def expectedParameters(expected):
        (
            FLOAT_ELEMENT(expected)
            .key("alarmThreshold")
            .displayedName("Alarm Threshold")
            .description("Alarm threshold per pixel.")
            .assignmentMandatory()
            .reconfigurable()
            .commit(),

            FLOAT_ELEMENT(expected)
            .key("warnThreshold")
            .displayedName("Warning Threshold")
            .description("Warning threshold per pixel.")
            .assignmentMandatory()
            .reconfigurable()
            .commit(),

            UINT64_ELEMENT(expected)
            .key("alarmMaxCount")
            .displayedName("Alarm Max. Count")
            .description("Maximum number of pixel above alarm threshold.")
            .assignmentMandatory()
            .reconfigurable()
            .commit(),

            UINT64_ELEMENT(expected)
            .key("warnMaxCount")
            .displayedName("Warning Max. Count")
            .description("Maximum number of pixel above warn threshold.")
            .tags("managed")
            .assignmentMandatory()
            .reconfigurable()
            .commit(),

            UINT64_ELEMENT(expected)
            .key("frameAxis")
            .displayedName('Multi-frame axis')
            .description("Axis for frames. Used to take the max over "
                         "this axis.")
            .tags("managed")
            .assignmentOptional()
            .defaultValue(0)
            .reconfigurable()
            .commit(),

            # The reason for the node is compatibility with the saturation
            # monitor add-on in calng. That way a MDL device can use this
            # device, the add-on or the aggregated info from the add-on
            NODE_ELEMENT(expected)
            .key("saturationMonitor")
            .commit(),

            # OUTPUT VARIABLES
            BOOL_ELEMENT(expected)
            .key("saturationMonitor.alarm")
            .displayedName('Alarm')
            .description("Alarm condition triggered.")
            .readOnly()
            .commit(),

            UINT64_ELEMENT(expected)
            .key("saturationMonitor.alarmCount")
            .displayedName('Alarm Counts')
            .description(
                "Total number of pixels above alarm threshold. Each pixel "
                "is only counted once even if it exceeds the threshold in "
                "multiple frames (/ memory cells = given axis)."
            )
            .readOnly()
            .commit(),

            BOOL_ELEMENT(expected)
            .key("saturationMonitor.warning")
            .displayedName('Warning')
            .description("Warning condition triggered.")
            .readOnly()
            .commit(),

            UINT64_ELEMENT(expected)
            .key("saturationMonitor.warnCount")
            .description(
                "Total number of pixels above warning threshold. Each pixel "
                "is only counted once even if it exceeds the threshold in "
                "multiple frames (/ memory cells = given axis)."
            )
            .description("Pixels above threshold.")
            .readOnly()
            .commit(),

            FLOAT_ELEMENT(expected)
            .key("saturationMonitor.maxValue")
            .displayedName("Max. Value")
            .description("Maximum value on one pixel.")
            .readOnly()
            .commit(),

            UINT64_ELEMENT(expected)
            .key("trainID")
            .displayedName('Train ID')
            .readOnly()
            .commit(),

        )

    def __init__(self, configuration):
        # always call superclass constructor first!
        super().__init__(configuration)

        # Register call-backs
        self.KARABO_ON_EOS("input", self.onEndOfStream)

    ##############################################
    #   Implementation of Callbacks              #
    ##############################################

    def onData(self, data, metaData):
        first_image = False
        if self['state'] == State.ON:
            self.logger.info("Start of Stream")
            self.updateState(State.PROCESSING)
            first_image = True

        try:
            image_path = self['imagePath']
            if data.has(image_path):
                image_data = data[image_path]
            else:
                raise RuntimeError("data does not contain any image")
        except Exception as e:
            msg = f"Exception caught in onData: {e}"
            self.update_count(error=True, status=msg)
            return

        ts = Timestamp.fromHashAttributes(
            metaData.getAttributes('timestamp'))

        if first_image:
            self.is_image_data = isinstance(image_data, ImageData)

        self.process_image(image_data, ts, first_image)  # Process image

    def process_image(self, image_data, ts, first_image):
        self.refresh_frame_rate_in()
        try:
            if not self.is_image_data:
                image_data = ImageData(image_data)

            pixels = image_data.getData()  # np.ndarray

            dimension = pixels.ndim
            # handling multiple frames: take max over frame axis
            if dimension > 2:
                max_image = np.nanmax(pixels, axis=self.get("frameAxis"))
            else:
                max_image = pixels
            # count pixel above thresholds
            nb_pix_a = int(np.nansum(max_image > self.get("alarmThreshold")))
            nb_pix_w = int(np.nansum(max_image > self.get("warnThreshold")))
            nb_max = float(np.nanmax(max_image))

            h = Hash()

            if nb_pix_a > self.get("alarmMaxCount"):
                h["saturationMonitor.alarm"] = True
                h["saturationMonitor.alarmCount"] = int(nb_pix_a)
                h["trainID"] = ts.getTid()
                # only update image if above threshold
                # that means last offending image will always be shown
                # TODO: check if that is good behaviour or misleading,
                # maybe image should always update
                # image with pixel above alarm threshold
                max_image[max_image <= self.get("alarmThreshold")] = 0
                image_data.setData(max_image)
                if first_image:
                    self.updateOutputSchema(image_data)
                self.writeImageToOutputs(image_data, ts)

            else:
                h["saturationMonitor.alarm"] = False
                h["saturationMonitor.warnCount"] = int(nb_pix_w)
            if nb_pix_w > self.get("warnMaxCount"):
                h["saturationMonitor.warning"] = True
            else:
                h["saturationMonitor.warning"] = False

            h["saturationMonitor.maxValue"] = int(nb_max)

            self.set(h, ts)

            self.update_count()  # Success
            self.refresh_frame_rate_out()

        except Exception as e:
            msg = f"Exception caught in process_image: {e}"
            self.update_count(error=True, status=msg)
