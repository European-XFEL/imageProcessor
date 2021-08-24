#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on August 24, 2021
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

from karabo.bound import (
    BOOL_ELEMENT, ImageData, INT32_ELEMENT, KARABO_CLASSINFO, NODE_ELEMENT,
    State, Timestamp, UINT32_ELEMENT
)

from image_processing.crosshair import crosshair

try:
    from .common import ImageProcOutputInterface
    from .ImageProcessorBase import ImageProcessorBase
    from ._version import version as deviceVersion
except ImportError:
    from imageProcessor.common import ImageProcOutputInterface
    from imageProcessor.ImageProcessorBase import ImageProcessorBase
    from imageProcessor._version import version as deviceVersion


@KARABO_CLASSINFO("ImageCrosshair", deviceVersion)
class ImageCrosshair(ImageProcessorBase, ImageProcOutputInterface):

    @staticmethod
    def expectedParameters(expected):
        (
            NODE_ELEMENT(expected).key('crosshair')
            .displayedName("Crosshair")
            .commit(),

            BOOL_ELEMENT(expected).key("crosshair.enable")
            .displayedName("Enable Crosshair")
            .assignmentOptional().defaultValue(True)
            .reconfigurable()
            .commit(),

            UINT32_ELEMENT(expected).key("xPosition")
            .displayedName("Crosshair/Marker X Position")
            .assignmentOptional().defaultValue(0)
            .reconfigurable()
            .commit(),

            UINT32_ELEMENT(expected).key("yPosition")
            .displayedName("Crosshair/Marker Y Position")
            .assignmentOptional().defaultValue(0)
            .reconfigurable()
            .commit(),

            INT32_ELEMENT(expected).key("rotation")
            .displayedName("Crosshair/Marker Rotation")
            .assignmentOptional().defaultValue(0)
            .minInc(-90).maxInc(90)
            .reconfigurable()
            .commit(),

        )

    def __init__(self, configuration):
        # always call superclass constructor first!
        super().__init__(configuration)

        # Register call-backs
        self.KARABO_ON_DATA("input", self.onData)
        self.KARABO_ON_EOS("input", self.onEndOfStream)

    def onData(self, data, metaData):
        first_image = False
        if self['state'] == State.ON:
            self.log.INFO("Start of Stream")
            self.updateState(State.PROCESSING)
            first_image = True

        try:
            ts = Timestamp.fromHashAttributes(
                metaData.getAttributes('timestamp'))
            image_data = data['data.image']

            self.refresh_frame_rate_in()

            # XXX superimpose crosshair and marker to data
            if self['crosshair.enable']:
                # superimpose a cross-hair
                image = image_data.getData()  # np.ndarray
                center = (self['xPosition'], self['yPosition'])
                angle = self['rotation']

                # auto-size, thickness and color
                ext_size = max(10, int(0.025 * max(image.shape)))
                int_size = ext_size // 3
                thickness = max(2, int(0.005 * max(image.shape)))
                ext_color = int(image.max())
                int_color = int(image.min())

                crosshair(image, center, ext_size, int_size, ext_color,
                          int_color, thickness, angle)

                image_data = ImageData(image)

            if first_image:
                # Update schema
                self.updateOutputSchema(image_data)

            self.writeImageToOutputs(image_data, ts)
            self.update_count()  # Success
            return

        except Exception as e:
            msg = "Exception caught in onData: {}".format(e)
            self.update_count(error=True, msg=msg)
            return

    def onEndOfStream(self, inputChannel):
        self.log.INFO("End of Stream")
        self['inFrameRate'] = 0.
        # Signals end of stream
        self.signalEndOfStreams()
        self.updateState(State.ON)
        self['status'] = 'ON'
