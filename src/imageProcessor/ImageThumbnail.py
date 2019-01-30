#############################################################################
# Author: <gabriele.giovanetti@xfel.eu>
# Created on December 19, 2018
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

from karabo.bound import (
    BOOL_ELEMENT, DOUBLE_ELEMENT, ImageData, IMAGEDATA_ELEMENT,
    INPUT_CHANNEL, KARABO_CLASSINFO, NODE_ELEMENT, OVERWRITE_ELEMENT,
    PythonDevice, Schema, State, Timestamp, Unit,
    VECTOR_INT32_ELEMENT,
)
from processing_utils.rate_calculator import RateCalculator

from image_processing.image_processing import thumbnail
from .common import ImageProcOutputInterface


@KARABO_CLASSINFO("ImageThumbnail", "2.3")
class ImageThumbnail(PythonDevice, ImageProcOutputInterface):

    @staticmethod
    def expectedParameters(expected):
        data = Schema()
        (
            OVERWRITE_ELEMENT(expected).key("state")
                .setNewOptions(State.ON, State.PROCESSING)
                .setNewDefaultValue(State.ON)
                .commit(),

            NODE_ELEMENT(data).key("data")
                .displayedName("Data")
                .commit(),

            IMAGEDATA_ELEMENT(data).key("data.image")
                .displayedName("Image")
                .commit(),

            INPUT_CHANNEL(expected).key("input")
                .displayedName("Input")
                .dataSchema(data)
                .commit(),

            # Images should be dropped if processor is too slow
            OVERWRITE_ELEMENT(expected).key("input.onSlowness")
                .setNewDefaultValue("drop")
                .commit(),

            DOUBLE_ELEMENT(expected).key("frameRate")
                .displayedName("Frame Rate")
                .description("The actual frame rate.")
                .unit(Unit.HERTZ)
                .readOnly()
                .commit(),

            VECTOR_INT32_ELEMENT(expected).key("thumbCanvas")
                .displayedName("Canvas")
                .description("Shape of canvas where thumbnail must fit: "
                             "[height (Y), width (X)]")
                .assignmentOptional().defaultValue([240, 180])
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
                .commit()

        )

    def __init__(self, configuration):
        # always call superclass constructor first!
        super(ImageThumbnail, self).__init__(configuration)

        # Register call-backs
        self.KARABO_ON_DATA("input", self.onData)
        self.KARABO_ON_EOS("input", self.onEndOfStream)

        # Variables for frames per second computation
        self.frame_rate = RateCalculator(refresh_interval=1.0)

    def onData(self, data, metaData):
        firstImage = False
        if self.get("state") == State.ON:
            self.log.INFO("Start of Stream")
            self.updateState(State.PROCESSING)
            firstImage = True

        try:
            if data.has('data.image'):
                imageData = data['data.image']
            elif data.has('image'):
                # To ensure backward compatibility
                # with older versions of cameras
                imageData = data['image']
            else:
                self.log.DEBUG("data does not have any image")
                return

            ts = Timestamp.fromHashAttributes(
                metaData.getAttributes('timestamp'))

            canvas = self.get("thumbCanvas")
            self.refreshFrameRate()

            data = imageData.getData()  # np.ndarray
            bpp = imageData.getBitsPerPixel()
            encoding = imageData.getEncoding()
            d_type = str(data.dtype)

            resample = self.get('resample')
            thumb_array = thumbnail(data, canvas,
                                    resample=resample).astype(d_type)

            thumb_img = ImageData(thumb_array, bitsPerPixel=bpp,
                                  encoding=encoding)

            if firstImage:
                # Update schema
                self.updateOutputSchema(thumb_img)

            self.writeImageToOutputs(thumb_img, ts)

        except Exception as e:
            self.log.ERROR("Exception caught in onData: %s" % str(e))

    def onEndOfStream(self, inputChannel):
        self.log.INFO("End of Stream")
        self.set("frameRate", 0.)
        # Signals end of stream
        self.signalEndOfStreams()
        self.updateState(State.ON)

    def refreshFrameRate(self):
        self.frame_rate.update()
        fps = self.frame_rate.refresh()
        if fps:
            self['frameRate'] = fps
            self.log.DEBUG('Input rate %f Hz' % fps)
