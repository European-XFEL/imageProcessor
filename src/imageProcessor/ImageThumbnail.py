#############################################################################
# Author: <gabriele.giovanetti@xfel.eu>
# Created on December 19, 2018
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################

from image_processing.image_processing import thumbnail
from karabo.bound import (
    BOOL_ELEMENT, KARABO_CLASSINFO, VECTOR_INT32_ELEMENT, ImageData)

from ._version import version as deviceVersion
from .common import ImageProcOutputInterface
from .ImageProcessorBase import ImageProcessorBase


@KARABO_CLASSINFO("ImageThumbnail", deviceVersion)
class ImageThumbnail(ImageProcessorBase, ImageProcOutputInterface):

    @staticmethod
    def expectedParameters(expected):
        (
            VECTOR_INT32_ELEMENT(expected).key("thumbCanvas")
            .displayedName("Canvas")
            .description("Shape of canvas where thumbnail must fit: "
                         "[height (Y), width (X)]")
            .assignmentOptional().defaultValue([180, 240])
            .minSize(2).maxSize(2)
            .reconfigurable()
            .commit(),

            BOOL_ELEMENT(expected).key("resample")
            .displayedName("Resample")
            .description("Binned pixels are averaged. Set to true for "
                         "better quality thumbnail, at the price of "
                         "higher CPU load")
            .assignmentOptional().defaultValue(False)
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
        data = image_data.getData()  # np.ndarray
        bpp = image_data.getBitsPerPixel()
        encoding = image_data.getEncoding()
        d_type = str(data.dtype)

        canvas = self['thumbCanvas']
        resample = self['resample']
        thumb_array = thumbnail(
            data, canvas, resample=resample).astype(d_type)

        return ImageData(thumb_array, bitsPerPixel=bpp, encoding=encoding)
