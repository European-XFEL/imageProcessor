#############################################################################
# Author: <gabriele.giovanetti@xfel.eu>
# Created on December 19, 2018
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################

from image_processing.image_processing import thumbnail
from karabo.bound import (
    BOOL_ELEMENT, KARABO_CLASSINFO, VECTOR_INT32_ELEMENT, ImageData, State,
    Timestamp)

try:
    from ._version import version as deviceVersion
    from .common import ImageProcOutputInterface
    from .ImageProcessorBase import ImageProcessorBase
except ImportError:
    from imageProcessor._version import version as deviceVersion
    from imageProcessor.common import ImageProcOutputInterface
    from imageProcessor.ImageProcessorBase import ImageProcessorBase


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
        self.KARABO_ON_DATA("input", self.onData)
        self.KARABO_ON_EOS("input", self.onEndOfStream)

    def onData(self, data, metaData):
        first_image = False
        if self['state'] == State.ON:
            self.log.INFO("Start of Stream")
            self.updateState(State.PROCESSING)
            first_image = True

        try:
            image_path = self['imagePath']
            if data.has(image_path):
                image_data = data[image_path]
            else:
                raise RuntimeError("data does not contain any image")

            ts = Timestamp.fromHashAttributes(
                metaData.getAttributes('timestamp'))

            self.refresh_frame_rate_in()

            data = image_data.getData()  # np.ndarray
            bpp = image_data.getBitsPerPixel()
            encoding = image_data.getEncoding()
            d_type = str(data.dtype)

            canvas = self['thumbCanvas']
            resample = self['resample']
            thumb_array = thumbnail(data, canvas,
                                    resample=resample).astype(d_type)

            thumb_img = ImageData(thumb_array, bitsPerPixel=bpp,
                                  encoding=encoding)

            if first_image:
                # Update schema
                self.updateOutputSchema(thumb_img)

            self.writeImageToOutputs(thumb_img, ts)
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
