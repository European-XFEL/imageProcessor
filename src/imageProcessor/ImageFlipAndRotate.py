#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on March 7, 2025
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################

from image_processing.image_processing import (
    imageFlipAlongX, imageFlipAlongY, imageRotate)
from karabo.bound import (
    BOOL_ELEMENT, INT32_ELEMENT, KARABO_CLASSINFO, NODE_ELEMENT, ImageData,
    Unit)

from ._version import version as deviceVersion
from .common import ImageProcOutputInterface
from .ImageProcessorBase import ImageProcessorBase


@KARABO_CLASSINFO("ImageFlipAndRotate", deviceVersion)
class ImageFlipAndRotate(ImageProcessorBase, ImageProcOutputInterface):

    @staticmethod
    def expectedParameters(expected):
        (
            NODE_ELEMENT(expected).key("flip")
            .displayedName("Image Flip")
            .description("Enables mirroring of the image.")
            .commit(),

            BOOL_ELEMENT(expected).key("flip.x")
            .displayedName("Horizontal Flip")
            .description("Enable horizontal flip. This is applied before the "
                         "image rotation.")
            .assignmentOptional().defaultValue(False)
            .reconfigurable()
            .commit(),

            BOOL_ELEMENT(expected).key("flip.y")
            .displayedName("Vertical Flip")
            .description("Enable vertical flip. This is applied before the "
                         "image rotation.")
            .assignmentOptional().defaultValue(False)
            .reconfigurable()
            .commit(),

            INT32_ELEMENT(expected).key("rotation")
            .displayedName("Image Rotation")
            .description("The image rotation. The angle must be a multiple of "
                         "90°. The rotation is done after the image flip.")
            .assignmentOptional().defaultValue(0)
            .options([0, 90, 180, 270])
            .unit(Unit.DEGREE)
            .reconfigurable()
            .commit(),
        )

    def __init__(self, configuration):
        # always call superclass constructor first!
        super().__init__(configuration)

        # Register call-backs
        self.KARABO_ON_EOS("input", self.onEndOfStream)

    # Overrides ImageProcessorBase.process_image
    def process_image(self, image_data, ts):
        flip_x = self["flip.x"]
        flip_y = self["flip.y"]
        rotation = self["rotation"]

        if flip_x or flip_y or rotation != 0:
            data = image_data.getData()  # np.ndarray
            if flip_x:
                data = imageFlipAlongX(data)
            if flip_y:
                data = imageFlipAlongY(data)
            if rotation != 0:
                data = imageRotate(data, rotation)

            return ImageData(data)

        else:
            return image_data
