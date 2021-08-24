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

            BOOL_ELEMENT(expected).key("crosshair.autoSize")
            .displayedName("Auto-Size")
            .assignmentOptional().defaultValue(True)
            .reconfigurable()
            .commit(),

            UINT32_ELEMENT(expected).key("crosshair.extSize")
            .displayedName("Ext Crosshair Size")
            .assignmentOptional().defaultValue(30)
            .reconfigurable()
            .commit(),

            UINT32_ELEMENT(expected).key("crosshair.intSize")
            .displayedName("Int Crosshair Size")
            .assignmentOptional().defaultValue(10)
            .reconfigurable()
            .commit(),

            BOOL_ELEMENT(expected).key("crosshair.autoThickness")
            .displayedName("Auto-Thickness")
            .assignmentOptional().defaultValue(True)
            .reconfigurable()
            .commit(),

            UINT32_ELEMENT(expected).key("crosshair.thickness")
            .displayedName("Crosshair Thickness")
            .assignmentOptional().defaultValue(5)
            .reconfigurable()
            .commit(),

            BOOL_ELEMENT(expected).key("crosshair.autoColor")
            .displayedName("Auto-Color")
            .assignmentOptional().defaultValue(True)
            .reconfigurable()
            .commit(),

            UINT32_ELEMENT(expected).key("crosshair.extColor")
            .displayedName("Ext Crosshair 'Color'")
            .assignmentOptional().defaultValue(65535)
            .reconfigurable()
            .commit(),

            UINT32_ELEMENT(expected).key("crosshair.intColor")
            .displayedName("Int Crosshair 'Color'")
            .assignmentOptional().defaultValue(0)
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

            if self['crosshair.enable']:
                # superimpose a cross-hair
                image = image_data.getData()  # np.ndarray
                center = (self['xPosition'], self['yPosition'])
                angle = self['rotation']

                if self['crosshair.autoSize']:
                    ext_size = max(10, int(0.025 * max(image.shape)))
                    int_size = ext_size // 3
                else:
                    ext_size = self['crosshair.extSize']
                    int_size = self['crosshair.intSize']

                if self['crosshair.autoThickness']:
                    thickness = max(2, int(0.005 * max(image.shape)))
                else:
                    thickness = self['crosshair.thickness']

                if self['crosshair.autoColor']:
                    ext_color = int(image.max())
                    int_color = int(image.min())
                else:
                    ext_color = self['crosshair.extColor']
                    int_color = self['crosshair.intColor']

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
