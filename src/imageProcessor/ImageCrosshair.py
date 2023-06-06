#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on August 24, 2021
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################

from image_processing import crosshair, marker
from karabo.bound import (
    BOOL_ELEMENT, INT32_ELEMENT, KARABO_CLASSINFO, NODE_ELEMENT,
    STRING_ELEMENT, UINT32_ELEMENT, VECTOR_STRING_ELEMENT,
    VECTOR_UINT32_ELEMENT, Hash, ImageData, State, Timestamp, Unit)

try:
    from ._version import version as deviceVersion
    from .common import ImageProcOutputInterface
    from .ImageProcessorBase import ImageProcessorBase
    from .scenes import get_scene
except ImportError:
    from imageProcessor._version import version as deviceVersion
    from imageProcessor.common import ImageProcOutputInterface
    from imageProcessor.ImageProcessorBase import ImageProcessorBase
    from imageProcessor.scenes import get_scene


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
            .description("The crosshair size will be calculated from the "
                         "image size.")
            .assignmentOptional().defaultValue(True)
            .reconfigurable()
            .commit(),

            UINT32_ELEMENT(expected).key("crosshair.extSize")
            .displayedName("Cross-Hair Size")
            .assignmentOptional().defaultValue(30)
            .unit(Unit.PIXEL)
            .reconfigurable()
            .commit(),

            UINT32_ELEMENT(expected).key("crosshair.intSize")
            .displayedName("Crosshair Transparency Size")
            .description("If larger than 0, this will be taken as the size of "
                         "the transparent center of the cross-hair.")
            .assignmentOptional().defaultValue(10)
            .unit(Unit.PIXEL)
            .reconfigurable()
            .commit(),

            BOOL_ELEMENT(expected).key("crosshair.autoThickness")
            .displayedName("Auto-Thickness")
            .description("The crosshair thickness will be calculated from the "
                         "image size.")
            .assignmentOptional().defaultValue(True)
            .reconfigurable()
            .commit(),

            UINT32_ELEMENT(expected).key("crosshair.thickness")
            .displayedName("Crosshair Thickness")
            .assignmentOptional().defaultValue(5)
            .unit(Unit.PIXEL)
            .reconfigurable()
            .commit(),

            BOOL_ELEMENT(expected).key("crosshair.autoColor")
            .displayedName("Auto-Color")
            .description("The image min value will be used for the crosshair "
                         "'color'.")
            .assignmentOptional().defaultValue(True)
            .reconfigurable()
            .commit(),

            UINT32_ELEMENT(expected).key("crosshair.color")
            .displayedName("Crosshair 'Color'")
            .assignmentOptional().defaultValue(65535)
            .hex()
            .reconfigurable()
            .commit(),

            NODE_ELEMENT(expected).key('marker')
            .displayedName("Marker")
            .commit(),

            BOOL_ELEMENT(expected).key("marker.enable")
            .displayedName("Enable Marker")
            .assignmentOptional().defaultValue(True)
            .reconfigurable()
            .commit(),

            STRING_ELEMENT(expected).key("marker.type")
            .displayedName("Marker Type")
            .options("rectangle,ellipse")
            .assignmentOptional().defaultValue('rectangle')
            .reconfigurable()
            .commit(),

            UINT32_ELEMENT(expected).key("marker.width")
            .displayedName("Marker Width")
            .assignmentOptional().defaultValue(20)
            .unit(Unit.PIXEL)
            .reconfigurable()
            .commit(),

            UINT32_ELEMENT(expected).key("marker.height")
            .displayedName("Marker Height")
            .assignmentOptional().defaultValue(20)
            .unit(Unit.PIXEL)
            .reconfigurable()
            .commit(),

            BOOL_ELEMENT(expected).key("marker.autoThickness")
            .displayedName("Auto-Thickness")
            .description("The marker thickness will be calculated from the "
                         "image size.")
            .assignmentOptional().defaultValue(True)
            .reconfigurable()
            .commit(),

            UINT32_ELEMENT(expected).key("marker.thickness")
            .displayedName("Marker Thickness")
            .assignmentOptional().defaultValue(5)
            .unit(Unit.PIXEL)
            .reconfigurable()
            .commit(),

            BOOL_ELEMENT(expected).key("marker.autoColor")
            .displayedName("Auto-Color")
            .description("The image min value will be used for the marker "
                         "'color'.")
            .assignmentOptional().defaultValue(True)
            .reconfigurable()
            .commit(),

            UINT32_ELEMENT(expected).key("marker.color")
            .displayedName("Marker 'Color'")
            .assignmentOptional().defaultValue(0)
            .hex()
            .reconfigurable()
            .commit(),

            VECTOR_UINT32_ELEMENT(expected).key("position")
            .setSpecialDisplayType("crosshair")
            .displayedName("Crosshair/Marker Position")
            .description("The position of the crosshair and/or markeri: [X, "
                         "Y].")
            .assignmentOptional().defaultValue([0, 0])
            .minSize(2).maxSize(2)
            .unit(Unit.PIXEL)
            .reconfigurable()
            .commit(),

            INT32_ELEMENT(expected).key("rotation")
            .displayedName("Crosshair/Marker Rotation")
            .assignmentOptional().defaultValue(0)
            .minInc(-90).maxInc(90)
            .unit(Unit.DEGREE)
            .reconfigurable()
            .commit(),

            VECTOR_STRING_ELEMENT(expected).key("availableScenes")
            .displayedName("Available Scenes")
            .description("Provides a scene for the Configuration Manager.")
            .setSpecialDisplayType("Scenes")
            .readOnly().initialValue(['scene'])
            .commit(),
        )

    def __init__(self, configuration):
        # always call superclass constructor first!
        super().__init__(configuration)

        # Register call-backs
        self.KARABO_ON_DATA("input", self.onData)
        self.KARABO_ON_EOS("input", self.onEndOfStream)

        self.KARABO_SLOT(self.requestScene)

    def requestScene(self, params):
        """Fulfill a scene request from another device.

        :param params: A `Hash` containing the method parameters
        """
        payload = Hash('success', False)
        name = params.get('name', default='')
        if name == 'scene':
            payload.set('success', True)
            payload.set('name', name)
            payload.set('data', get_scene(self.getInstanceId()))

        self.reply(Hash('type', 'deviceScene',
                        'origin', self.getInstanceId(),
                        'payload', payload))

    def superimpose_crosshair(self, image):
        """Superimpose a crosshair to the image"""

        if not self['crosshair.enable']:
            return

        center = self['position']
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
            color = None
        else:
            color = self['crosshair.color']

        crosshair(image, center, ext_size, int_size, color, thickness, angle)

    def superimpose_marker(self, image):
        """Superimpose a marker to the image"""

        if not self['marker.enable']:
            return

        center = self['position']
        angle = self['rotation']
        marker_type = self['marker.type']
        shape = (self['marker.width'], self['marker.height'])

        if self['marker.autoThickness']:
            thickness = max(1, int(0.005 * max(image.shape)))
        else:
            thickness = self['marker.thickness']

        if self['marker.autoColor']:
            color = None
        else:
            color = self['marker.color']

        marker(image, marker_type, center, shape, color, thickness, angle)

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
            image = image_data.getData()  # np.ndarray

            self.refresh_frame_rate_in()

            self.superimpose_crosshair(image)

            self.superimpose_marker(image)

            image_data = ImageData(image)

            if first_image:
                # Update schema
                self.updateOutputSchema(image_data)

            self.writeImageToOutputs(image_data, ts)
            self.update_count()  # Success
            self.refresh_frame_rate_out()
            return

        except Exception as e:
            msg = f"Exception caught in onData: {e}"
            self.update_count(error=True, status=msg)
            return

    def onEndOfStream(self, inputChannel):
        self.log.INFO("End of Stream")
        self['inFrameRate'] = 0.
        # Signals end of stream
        self.signalEndOfStreams()
        self.updateState(State.ON)
        self['status'] = 'Idle'
