#############################################################################
# Author: gabriele.giovanetti@xfel.eu
# Created on September 7, 2018, 12:00 PM
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

from collections import deque

from threading import Lock

from karabo.bound import (
    BOOL_ELEMENT, DOUBLE_ELEMENT, INT32_ELEMENT, INPUT_CHANNEL,
    KARABO_CLASSINFO, OVERWRITE_ELEMENT, Schema, State, Timestamp, Unit,
    UINT32_ELEMENT
)

from processing_utils.rate_calculator import RateCalculator


try:
    from .common import ImageProcOutputInterface
    from .ImageProcessorBase import ImageProcessorBase
except ImportError:
    from imageProcessor.common import ImageProcOutputInterface
    from imageProcessor.ImageProcessorBase import ImageProcessorBase


@KARABO_CLASSINFO("ImagePicker", "2.6")
class ImagePicker(ImageProcessorBase, ImageProcOutputInterface):
    """
    This device has two input channels (inputImage and inputTrainid).
    inputImage expects an image stream (e.g. from a camera)
    inputTrainId is used to get its timestamp
    images whose train ID equals inputTrainId + trainIdOffset are forwarded to
    output channel, while others are discarded.

    """

    @staticmethod
    def expectedParameters(expected):
        (
            INPUT_CHANNEL(expected).key("inputTrainId")
            .displayedName("Input Train ID")
            .dataSchema(Schema())
            .commit(),

            BOOL_ELEMENT(expected).key("isDisabled")
            .displayedName("Disabled")
            .description("When disabled, all images received in input are"
                         "forwarded to output channel.")
            .assignmentOptional().defaultValue(False)
            .reconfigurable()
            .commit(),

            # Images should be dropped if processor is too slow
            OVERWRITE_ELEMENT(expected).key("inputTrainId.onSlowness")
            .setNewDefaultValue("drop")
            .commit(),

            DOUBLE_ELEMENT(expected).key('outFrameRate')
            .displayedName('Output Frame Rate')
            .description('The output frame rate.')
            .unit(Unit.HERTZ)
            .readOnly()
            .commit(),

            INT32_ELEMENT(expected).key("trainIdOffset")
            .displayedName("Train ID Offset")
            .description("Positive: output image train ID is greater than "
                         "input train ID (delay). "
                         "Negative: output image train ID is lower than "
                         "input train (advance)")
            .assignmentOptional().defaultValue(0)
            .reconfigurable()
            .commit(),

            UINT32_ELEMENT(expected).key("imgBufferSize")
            .displayedName("Images Buffer Size")
            .description("Number of images to be kept waiting for "
                         "a matching train ID.")
            .minInc(1)
            .assignmentOptional().defaultValue(5)
            .init()
            .commit(),

            UINT32_ELEMENT(expected).key("trainIdBufferSize")
            .displayedName("Train IDs Buffer Size")
            .description("Number of train IDs to be kept waiting for an "
                         "image with matching train ID.")
            .minInc(1)
            .assignmentOptional().defaultValue(5)
            .init()
            .commit(),
        )

    def __init__(self, configuration):
        # always call superclass constructor first!
        super(ImagePicker, self).__init__(configuration)

        # frames per second
        self.last_time = None
        self.counter = 0

        self.image_buffer = None
        self.tid_buffer = None
        self.buffer_lock = Lock()

        self.is_channel_active = {'inputImage': False, 'inputTrainId': False}

        # Register call-backs
        self.KARABO_ON_DATA("input", self.onDataImage)
        self.KARABO_ON_EOS("input", self.onEndOfStream)
        self.KARABO_ON_DATA("inputTrainId", self.onDataTrainId)
        self.KARABO_ON_EOS("inputTrainId", self.onEndOfStream)

        self.registerInitialFunction(self.initialization)

        # Variables for frames per second computation
        self.frame_rate_out = RateCalculator(refresh_interval=1.0)

    def initialization(self):
        """ This method will be called after the constructor. """
        self.image_buffer = deque(maxlen=self['imgBufferSize'])
        self.tid_buffer = deque(maxlen=self['trainIdBufferSize'])

    def isActive(self):
        return any(self.is_channel_active.values())

    def onDataImage(self, data, metaData):
        if self.image_buffer is None:
            return

        if self.is_channel_active['inputImage'] is False:
            self.is_channel_active['inputImage'] = True
            self.log.INFO("Start of Image Stream")
        if self['state'] == State.ON:
            self.updateState(State.PROCESSING)

        try:
            if data.has('data.image'):
                image_data = data['data.image']
            elif data.has('image'):
                # To ensure backward compatibility
                # with older versions of cameras
                image_data = data['image']
            else:
                raise RuntimeError("data does not contain any image")
        except Exception as e:
            msg = "Exception caught in onData: {}".format(e)
            self.update_warn(error=True, msg=msg)
            return

        self.updateOutputSchema(image_data)

        self.refresh_frame_rate_in()

        try:
            ts = Timestamp.fromHashAttributes(
                metaData.getAttributes('timestamp'))

            if self['isDisabled']:
                self.writeImageToOutputs(image_data, ts)
                self.update_warn()  # Success
                self.refresh_frame_rate_out()
                return
            else:
                # if match is found image is sent on output channel
                # otherwise it is queued
                if not self.searchForMatch(
                        {'ts': ts, 'imageData': image_data}):
                    with self.buffer_lock:
                        self.image_buffer.append(
                            {'ts': ts, 'imageData': image_data})

        except Exception as e:
            msg = "Exception caught in onData: {}".format(e)
            self.update_warn(error=True, msg=msg)

    def onDataTrainId(self, data, metaData):
        if self.tid_buffer is None:
            return

        if self['isDisabled']:
            return

        if self.is_channel_active['inputTrainId'] is False:
            self.is_channel_active['inputTrainId'] = True
            self.log.INFO("Start of Train ID Stream")
        if self['state'] == State.ON:
            self.updateState(State.PROCESSING)

        ts = Timestamp.fromHashAttributes(
            metaData.getAttributes('timestamp'))
        tid = ts.getTrainId()

        with self.buffer_lock:
            self.tid_buffer.append(tid)

        self.searchForMatch(ts)

    def searchForMatch(self, item):
        """
        Output data if match is found

        If item is a timestamp, it searches for images in self.imageBuffer
           queue where train ID matches
        if item has the form {timestamp: image_data} it searches if it matches
           any of the queued train IDs in self.trainidBuffer

        if match is found returns True, False otherwise

        Assumptions:
        - train IDs and images are ordered (i.e. timestamps are not decreasing)
        - there may be more images with same trainid (e.g. frameRate > 10Hz)
        - on train ID channel no trainid is received more than once
        """
        match_found = False
        offset = self['trainIdOffset']
        if isinstance(item, Timestamp):
            tid = item.getTrainId()
            with self.buffer_lock:
                for img in self.image_buffer:
                    img_tid = img['ts'].getTrainId()
                    if img_tid == tid + offset:
                        match_found = True
                        self.writeImageToOutputs(img['imageData'], img['ts'])
                        self.update_warn()  # Success
                        self.refresh_frame_rate_out()
                        return
                    elif img_tid > tid + offset:
                        break
                self.cleanup_image_queue(tid)
        else:
            try:
                img = item
                img_tid = img['ts'].getTrainId()
                for tid in self.tid_buffer:
                    if img_tid == tid + offset:
                        match_found = True
                        self.writeImageToOutputs(img['imageData'], img['ts'])
                        self.update_warn()  # Success
                        self.refresh_frame_rate_out()
                        return
                    elif img_tid < tid + offset:
                        break
            except Exception as e:
                raise RuntimeError("searchForMatch() got unexpected "
                                   "exception: {}".format(e))

        return match_found

    def refresh_frame_rate_out(self):
        self.frame_rate_out.update()
        fps_out = self.frame_rate_out.refresh()
        if fps_out:
            self['outFrameRate'] = fps_out
            self.log.DEBUG("Output rate {} Hz".format(fps_out))

    def cleanup_image_queue(self, tid):
        """
        Remove from image queue images with older train ID

        should be called with self.buffer_lock acquired
        """
        while self.image_buffer[0]['ts'].getTrainId() <= tid:
            self.image_buffer.popleft()
            if not self.image_buffer:
                break

    def onEndOfStream(self, inputChannel):
        self.log.INFO("End of Stream on channel {}".format(inputChannel))

        self.is_channel_active[inputChannel] = False
        self['errorCount'] = 0

        if inputChannel == 'imageInput':
            self['inFrameRate'] = 0
            self['outFrameRate'] = 0
            self.signalEndOfStreams()

        if not self.isActive():
            # Signals end of stream
            self.updateState(State.ON)
            self['status'] = 'ON'
