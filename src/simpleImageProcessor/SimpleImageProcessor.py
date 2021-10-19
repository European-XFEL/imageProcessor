#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on April  6, 2016
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################
import math
import time

from image_processing import image_processing
from karabo.bound import (
    BOOL_ELEMENT, DOUBLE_ELEMENT, FLOAT_ELEMENT, IMAGEDATA_ELEMENT,
    INPUT_CHANNEL, INT32_ELEMENT, KARABO_CLASSINFO, OVERWRITE_ELEMENT,
    SLOT_ELEMENT, STRING_ELEMENT, VECTOR_STRING_ELEMENT, Hash, MetricPrefix,
    PythonDevice, Schema, State, Unit)
from karabo.common.scenemodel.api import (
    BoxLayoutModel, CheckBoxModel, ComboBoxModel, DisplayLabelModel,
    DisplayStateColorModel, DoubleLineEditModel, ErrorBoolModel, LabelModel,
    LineModel, ScatterGraphModel, SceneModel, StickerModel, TrendGraphModel,
    write_scene)

from ._version import version


@KARABO_CLASSINFO("SimpleImageProcessor", version)
class SimpleImageProcessor(PythonDevice):
    # Numerical factor to convert Gaussian standard deviation to beam size
    STD_TO_FWHM = 2.35

    @staticmethod
    def expectedParameters(expected):
        data = Schema()
        (
            OVERWRITE_ELEMENT(expected).key("state")
            .setNewOptions(State.ON, State.PROCESSING)
            .setNewDefaultValue(State.ON)
            .commit(),

            VECTOR_STRING_ELEMENT(expected).key("interfaces")
            .displayedName("Interfaces")
            .readOnly()
            .initialValue(["Processor"])
            .commit(),

            SLOT_ELEMENT(expected).key("reset")
            .displayedName("Reset")
            .description("Resets the processor output values.")
            .commit(),

            IMAGEDATA_ELEMENT(data).key("image")
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

            INT32_ELEMENT(expected).key("imageSizeX")
            .displayedName("Image Width")
            .description("The image width.")
            .unit(Unit.PIXEL)
            .readOnly()
            .commit(),

            INT32_ELEMENT(expected).key("imageSizeY")
            .displayedName("Image Height")
            .description("The image height.")
            .unit(Unit.PIXEL)
            .readOnly()
            .commit(),

            INT32_ELEMENT(expected).key("offsetX")
            .displayedName("Image Offset X")
            .description("The image offset in X direction, i.e. the X "
                         "position of its top-left corner.")
            .adminAccess()
            .unit(Unit.PIXEL)
            .readOnly()
            .commit(),

            INT32_ELEMENT(expected).key("offsetY")
            .displayedName("Image Offset Y")
            .description("The image offset in Y direction, i.e. the Y "
                         "position of its top-left corner.")
            .adminAccess()
            .unit(Unit.PIXEL)
            .readOnly()
            .commit(),

            INT32_ELEMENT(expected).key("binningX")
            .displayedName("Image Binning X")
            .description("The image binning in X direction.")
            .unit(Unit.PIXEL)
            .readOnly()
            .commit(),

            INT32_ELEMENT(expected).key("binningY")
            .displayedName("Image Binning Y")
            .description("The image binning in Y direction.")
            .unit(Unit.PIXEL)
            .readOnly()
            .commit(),

            # Processor configuration

            FLOAT_ELEMENT(expected).key("pixelSize")
            .displayedName("Pixel Size")
            .description("The pixel size, to be used for converting the "
                         "fit's standard deviation to FWHM.")
            .unit(Unit.METER).metricPrefix(MetricPrefix.MICRO)
            .assignmentOptional().defaultValue(0.0)
            .minInc(0.0)
            .reconfigurable()
            .commit(),

            FLOAT_ELEMENT(expected).key("imageThreshold")
            .displayedName("Image Threshold")
            .description("The threshold for doing processing. Only images "
                         "having maximum pixel value above this threshold "
                         "will be processed.")
            .assignmentOptional().defaultValue(0.)
            .unit(Unit.NUMBER)
            .expertAccess()
            .init()
            .commit(),

            BOOL_ELEMENT(expected).key("subtractImagePedestal")
            .displayedName("Subtract Image Pedestal")
            .description("Subtract the image pedestal (ie image = image - "
                         "image.min()) before centre-of-mass and Gaussian "
                         "fit.")
            .assignmentOptional().defaultValue(True)
            .expertAccess()
            .init()
            .commit(),

            STRING_ELEMENT(expected).key("thresholdType")
            .displayedName("Pixel Threshold Type")
            .description("Defines whether an absolute or relative "
                         "thresholding is used in the calculations.")
            .assignmentOptional().defaultValue("None")
            .options("None Absolute Relative")
            .reconfigurable()
            .commit(),

            FLOAT_ELEMENT(expected).key("pixelThreshold")
            .displayedName("Pixel Threshold")
            .description("If Pixel threshold type is set to absolute, "
                         "pixels below this threshold will be set to 0 in "
                         "the processing of images. If it is set to "
                         "relative, pixels below this fraction of the "
                         "maximum pixel value will be set to zero (and "
                         "this property should be between 0 and 1). If "
                         "it is set to None, no thresholding will occur.")
            .assignmentOptional().defaultValue(0.1)
            .reconfigurable()
            .commit(),

            # Image processing outputs

            BOOL_ELEMENT(expected).key("success")
            .displayedName("Success")
            .description("Success boolean whether the image processing "
                         "was successful or not.")
            .readOnly().initialValue(False)
            .commit(),

            DOUBLE_ELEMENT(expected).key("maxPxValue")
            .displayedName("Max Pixel Value")
            .description("Maximum pixel value.")
            .unit(Unit.NUMBER)
            .readOnly()
            .commit(),

            DOUBLE_ELEMENT(expected).key("amplitudeX")
            .displayedName("Amplitude X")
            .description("Amplitude X from Gaussian fit.")
            .unit(Unit.NUMBER)
            .readOnly()
            .commit(),

            DOUBLE_ELEMENT(expected).key("amplitudeY")
            .displayedName("Amplitude Y")
            .description("Amplitude Y from Gaussian fit.")
            .unit(Unit.NUMBER)
            .readOnly()
            .commit(),

            DOUBLE_ELEMENT(expected).key("positionX")
            .displayedName("Position X")
            .description("Beam position X from Gaussian fit.")
            .unit(Unit.PIXEL)
            .readOnly()
            .commit(),

            DOUBLE_ELEMENT(expected).key("positionY")
            .displayedName("Position Y")
            .description("Beam position Y from Gaussian fit.")
            .unit(Unit.PIXEL)
            .readOnly()
            .commit(),

            DOUBLE_ELEMENT(expected).key("sigmaX")
            .displayedName("Sigma X")
            .description("Standard deviation X from Gaussian fit.")
            .unit(Unit.PIXEL)
            .expertAccess()
            .readOnly()
            .commit(),

            DOUBLE_ELEMENT(expected).key("sigmaY")
            .displayedName("Sigma Y")
            .description("Standard deviation Y from Gaussian fit.")
            .unit(Unit.PIXEL)
            .expertAccess()
            .readOnly()
            .commit(),

            DOUBLE_ELEMENT(expected).key("fwhmX")
            .displayedName("FWHM X")
            .description("FWHM obtained from standard deviation.")
            .unit(Unit.METER).metricPrefix(MetricPrefix.MICRO)
            .readOnly()
            .commit(),

            DOUBLE_ELEMENT(expected).key("fwhmY")
            .displayedName("FWHM Y")
            .description("FWHM obtained from standard deviation.")
            .unit(Unit.METER).metricPrefix(MetricPrefix.MICRO)
            .readOnly()
            .commit(),

            DOUBLE_ELEMENT(expected).key("errPositionX")
            .displayedName("Error Position X")
            .description("Uncertainty on position X from Gaussian fit.")
            .expertAccess()
            .unit(Unit.PIXEL)
            .readOnly()
            .commit(),

            DOUBLE_ELEMENT(expected).key("errPositionY")
            .displayedName("Error Position Y")
            .description("Uncertainty on position Y from Gaussian fit.")
            .expertAccess()
            .unit(Unit.PIXEL)
            .readOnly()
            .commit(),

            DOUBLE_ELEMENT(expected).key("errSigmaX")
            .displayedName("Error Sigma X")
            .description("Uncertainty of the standard deviation X from "
                         "Gaussian fit.")
            .expertAccess()
            .unit(Unit.PIXEL)
            .readOnly()
            .commit(),

            DOUBLE_ELEMENT(expected).key("errSigmaY")
            .displayedName("Error Sigma Y")
            .description("Uncertainty of the standard deviation Y from "
                         "Gaussian fit.")
            .expertAccess()
            .unit(Unit.PIXEL)
            .readOnly()
            .commit(),

            VECTOR_STRING_ELEMENT(expected).key('availableScenes')
            .setSpecialDisplayType("Scenes")
            .readOnly().initialValue(['scene', 'link'])
            .commit(),
        )

    def initialization(self):
        """ This method will be called after the constructor. """
        self.reset()

    def preReconfigure(self, incomingReconfiguration):
        if incomingReconfiguration.has("thresholdType") or \
                incomingReconfiguration.has("pixelThreshold"):
            t_type = self.get("thresholdType")
            threshold = self.get("pixelThreshold")
            if incomingReconfiguration.has("thresholdType"):
                t_type = incomingReconfiguration["thresholdType"]
            if incomingReconfiguration.has("pixelThreshold"):
                threshold = incomingReconfiguration["pixelThreshold"]

            self._is_threshold_valid(t_type, threshold)

    def __init__(self, configuration):
        # always call superclass constructor first!
        super(SimpleImageProcessor, self).__init__(configuration)

        # 1d Gaussian fit parameters
        self.amplitudeX = None
        self.positionX = None
        self.sigmaX = None
        self.amplitudeY = None
        self.positionY = None
        self.sigmaY = None

        # Current image
        self.currentImage = None

        # frames per second
        self.lastTime = None
        self.counter = 0

        # Register additional slots
        self.registerSlot(self.reset)

        self._exception_log = False
        # Register call-backs
        self.KARABO_ON_DATA("input", self.onData)
        self.KARABO_ON_EOS("input", self.onEndOfStream)

        self.KARABO_SLOT(self.requestScene)
        self.registerInitialFunction(self.initialization)

        if self["pixelThreshold"] >= 1 and self["thresholdType"] == "Relative":
            msg = "Cannot initialize a device with a relative threshold " \
                  "greater than 1."
            self.log.ERROR(msg)
            raise ValueError(msg)

    def requestScene(self, params):
        """Fulfill a scene request from another device.

        NOTE: Required by Scene Supply Protocol, which is defined in KEP 21.
              The format of the reply is also specified there.

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

    def reset(self):
        h = Hash()

        h.set("maxPxValue", 0.0)
        h.set("amplitudeX", 0.0)
        h.set("positionX", 0.0)
        h.set("errPositionX", 0.0)
        h.set("sigmaX", 0.0)
        h.set("errSigmaX", 0.0)
        h.set("fwhmX", 0.0)
        h.set("amplitudeY", 0.0)
        h.set("positionY", 0.0)
        h.set("errPositionY", 0.0)
        h.set("sigmaY", 0.0)
        h.set("errSigmaY", 0.0)
        h.set("fwhmY", 0.0)
        # Reset device parameters (all at once)
        self.set(h)

    def onData(self, data, metaData):
        if self.get("state") == State.ON:
            self.log.INFO("Start of Stream")
            self.updateState(State.PROCESSING)

        if data.has('data.image'):
            self.processImage(data['data.image'])
        elif data.has('image'):
            # To ensure backward compatibility
            # with older versions of cameras
            self.processImage(data['image'])
        else:
            self.log.INFO("data does not have any image")

    def onEndOfStream(self, inputChannel):
        self.log.INFO("End of Stream")
        self.set("frameRate", 0.)
        self.updateState(State.ON)

    def processImage(self, imageData):
        img_threshold = self.get("imageThreshold")
        thr_type = self.get("thresholdType")
        pix_thr = self.get("pixelThreshold")

        h = Hash()  # Empty hash
        # default is no success in processing
        h.set("success", False)

        self.counter += 1
        currentTime = time.time()
        if self.lastTime is None:
            self.counter = 0
            self.lastTime = currentTime
        elif self.lastTime and (currentTime - self.lastTime) > 1.:
            fps = self.counter / (currentTime - self.lastTime)
            self.set("frameRate", fps)
            self.log.DEBUG("Acquisition rate %f Hz" % fps)
            self.counter = 0
            self.lastTime = currentTime

        pixelSize = self.get("pixelSize")

        dims = imageData.getDimensions()
        imageSizeY = dims[0]
        imageSizeX = dims[1]
        if imageSizeX != self.get("imageSizeX"):
            h.set("imageSizeX", imageSizeX)
        if imageSizeY != self.get("imageSizeY"):
            h.set("imageSizeY", imageSizeY)

        roiOffsets = imageData.getROIOffsets()
        offsetY = roiOffsets[0]
        offsetX = roiOffsets[1]
        if offsetX != self.get("offsetX"):
            h.set("offsetX", offsetX)
        if offsetY != self.get("offsetY"):
            h.set("offsetY", offsetY)

        try:
            binning = imageData.getBinning()
            binningY = binning[0]
            binningX = binning[1]
            if binningX != self.get("binningX"):
                h.set("binningX", binningX)
            if binningY != self.get("binningY"):
                h.set("binningY", binningY)
        except AttributeError:
            # Image has no binning information, for Karabo < 2.2.3
            binningY = 1
            binningX = 1

        self.currentImage = imageData.getData()  # np.ndarray
        img = self.currentImage  # Shallow copy
        if img.ndim == 3 and img.shape[2] == 1:
            # Image has 3rd dimension (channel), but it's 1
            self.log.DEBUG("Reshaping image...")
            img = img.squeeze()

        self.log.DEBUG("Image loaded!!!")

        # ---------------------
        # Filter by Threshold
        if img.max() < img_threshold:
            self.log.DEBUG("Max pixel value below threshold: image "
                           "discarded!")
            # set the hash for no success!
            self.set(h)
            return

        # ---------------------
        # Get pixel max value
        img_max = img.max()
        h.set("maxPxValue", float(img_max))
        self.log.DEBUG("Pixel max: done!")

        # ---------------------
        # Pedestal subtraction
        if self.get("subtractImagePedestal"):
            imgMin = img.min()
            if imgMin > 0:
                if self.currentImage is img:
                    # Must copy, or self.currentImage will be modified
                    self.currentImage = img.copy()

                # Subtract image pedestal
                img -= imgMin

            self.log.DEBUG("Image pedestal subtraction: done!")

        # ---------------------
        # Remove Noise

        if thr_type == "Absolute":
            if img.max() < pix_thr:
                self.log.DEBUG("Max pixel value below threshold: image "
                               "discarded!")
                # set the hash for no success!
                self.set(h)
                return
            img2 = image_processing. \
                imageSetThreshold(img, min(pix_thr, img.max()))

        elif thr_type == "Relative":
            img2 = image_processing. \
                imageSetThreshold(img, pix_thr * img.max())

        else:
            img2 = img

        # ------------------------------------------------
        # 1-D Gaussian Fits

        # ------------------------------------------------
        # X Fitting
        imgX = image_processing.imageSumAlongY(img2)

        # Initial parameters
        p0 = image_processing.peakParametersEval(imgX)

        # 1-d Gaussian fit
        try:
            out = image_processing.fitGauss(imgX, p0)
            self._exception_log = False
        except Exception as e:
            # Set Hash for no success, the fitting did not work, e.g. no
            # center found
            if not self._exception_log:
                self._exception_log = True
                self.log.ERROR(f"Error in fitting gaussian: {e}")
            self.set(h)
            return

        paramX = out[0]  # parameters
        covX = out[1]  # covariance
        successX = out[2]  # error

        # Save fit's parameters
        self.amplitudeX = paramX[0]
        self.positionX = paramX[1]
        self.sigmaX = paramX[2]

        # ------------------------------------------------
        # Y Fitting
        imgY = image_processing.imageSumAlongX(img2)

        # Initial parameters
        p0 = image_processing.peakParametersEval(imgY)

        # 1-d Gaussian fit
        out = image_processing.fitGauss(imgY, p0)
        paramY = out[0]  # parameters
        covY = out[1]  # covariance
        successY = out[2]  # error

        # Save fit's parameters
        self.amplitudeY = paramY[0]
        self.positionY = paramY[1]
        self.sigmaY = paramY[2]

        SUCCESS = (1, 2, 3, 4)
        if (successX in SUCCESS and successY in SUCCESS
                and covX is not None and covY is not None):

            # NOTE: Sometimes the covariance matrix elements provide negative
            # values. Hence, we declare no success
            if any(variance < 0. for variance
                   in (covX[1][1], covX[2][2], covY[1][1], covY[2][2])):
                self.set(h)
                return

            # Directly set the success boolean
            h.set("success", True)

            # ----------------
            # X Fit Update

            h.set("positionX", binningX * (paramX[1] + offsetX))
            h.set("errPositionX", math.sqrt(covX[1][1]))
            h.set("sigmaX", paramX[2])
            h.set("errSigmaX", math.sqrt(covX[2][2]))
            if pixelSize > 0:
                h.set("fwhmX", self.STD_TO_FWHM * pixelSize * paramX[2])

            h.set("amplitudeX", paramX[0] / paramY[2] / math.sqrt(2 * math.pi))

            # ----------------
            # Y Fit Update

            h.set("positionY", binningY * (paramY[1] + offsetY))
            h.set("errPositionY", math.sqrt(covY[1][1]))
            h.set("sigmaY", paramY[2])
            h.set("errSigmaY", math.sqrt(covY[2][2]))
            if pixelSize > 0:
                h.set("fwhmY", self.STD_TO_FWHM * pixelSize * paramY[2])

            h.set("amplitudeY", paramY[0] / paramX[2] / math.sqrt(2 * math.pi))

        self.log.DEBUG("1-d Gaussian fit: done!")

        # Update device parameters (all at once)
        self.set(h)

    def _is_threshold_valid(self, t_type, threshold):
        if t_type == "Relative" and threshold > 1:
            msg = "Cannot set a relative threshold greater than 1."
            self.log.ERROR(msg)
            self["status"] = msg
            raise ValueError(msg)


def get_scene(deviceId):
    default_font = 'Source Sans Pro,10,-1,5,50,0,0,0,0,0'
    scene00 = LabelModel(
        font=default_font, foreground='#000000',
        height=28.0,
        parent_component='DisplayComponent', text='Image Threshold',
        width=141.0, x=10.0, y=300.0)
    scene01 = LabelModel(
        font=default_font, foreground='#000000',
        height=28.0,
        parent_component='DisplayComponent', text='Subtract Image Pedestal',
        width=141.0, x=10.0, y=328.0)
    scene02 = LabelModel(
        font=default_font, foreground='#000000',
        height=28.0,
        parent_component='DisplayComponent', text='Pixel Threshold Type',
        width=141.0, x=10.0, y=356.0)
    scene03 = LabelModel(
        font=default_font, foreground='#000000',
        height=27.0,
        parent_component='DisplayComponent', text='Pixel Threshold',
        width=141.0, x=10.0, y=384.0)
    scene0 = BoxLayoutModel(
        direction=2, height=111.0, width=141.0,
        x=10.0, y=300.0, children=[scene00, scene01, scene02, scene03])
    scene100 = LabelModel(
        font=default_font, foreground='#000000',
        height=24.0,
        parent_component='DisplayComponent', text='Frame Rate',
        width=116.0, x=10.0, y=120.0)
    scene101 = LabelModel(
        font=default_font, foreground='#000000',
        height=23.0,
        parent_component='DisplayComponent', text='Image Width', width=116.0,
        x=10.0, y=144.0)
    scene102 = LabelModel(
        font=default_font, foreground='#000000',
        height=24.0,
        parent_component='DisplayComponent', text='Image Height',
        width=116.0, x=10.0, y=167.0)
    scene103 = LabelModel(
        font=default_font, foreground='#000000',
        height=23.0,
        parent_component='DisplayComponent', text='Image Offset X',
        width=116.0, x=10.0, y=191.0)
    scene104 = LabelModel(
        font=default_font, foreground='#000000',
        height=24.0,
        parent_component='DisplayComponent', text='Image Binning X',
        width=116.0, x=10.0, y=214.0)
    scene105 = LabelModel(
        font=default_font, foreground='#000000',
        height=23.0,
        parent_component='DisplayComponent', text='Image Binning Y',
        width=116.0, x=10.0, y=238.0)
    scene10 = BoxLayoutModel(
        direction=2, height=141.0, width=116.0, x=10.0, y=120.0, children=[
            scene100, scene101, scene102, scene103, scene104, scene105])
    scene110 = DisplayLabelModel(
        font_size=10, height=24.0, keys=[
            f'{deviceId}.frameRate'], parent_component='DisplayComponent',
        width=115.0, x=126.0, y=120.0)
    scene111 = DisplayLabelModel(
        font_size=10, height=23.0, keys=[
            f'{deviceId}.imageSizeX'], parent_component='DisplayComponent',
        width=115.0, x=126.0, y=144.0)
    scene112 = DisplayLabelModel(
        font_size=10, height=24.0, keys=[
            f'{deviceId}.imageSizeY'], parent_component='DisplayComponent',
        width=115.0, x=126.0, y=167.0)
    scene113 = DisplayLabelModel(
        font_size=10, height=23.0, keys=[
            f'{deviceId}.offsetX'], parent_component='DisplayComponent',
        width=115.0, x=126.0, y=191.0)
    scene114 = DisplayLabelModel(
        font_size=10, height=24.0, keys=[
            f'{deviceId}.binningX'], parent_component='DisplayComponent',
        width=115.0, x=126.0, y=214.0)
    scene115 = DisplayLabelModel(
        font_size=10, height=23.0, keys=[
            f'{deviceId}.binningY'], parent_component='DisplayComponent',
        width=115.0, x=126.0, y=238.0)
    scene11 = BoxLayoutModel(
        direction=2, height=141.0, width=115.0, x=126.0, y=120.0, children=[
            scene110, scene111, scene112, scene113, scene114, scene115])
    scene1 = BoxLayoutModel(
        height=141.0, width=231.0,
        x=10.0, y=120.0, children=[scene10, scene11])
    scene2 = LabelModel(
        font='Source Sans Pro,11,-1,5,50,0,1,0,0,0', height=20.0,
        parent_component='DisplayComponent', text='Image Properties',
        width=117.0, x=10.0, y=90.0)
    scene3 = LabelModel(
        font='Source Sans Pro,11,-1,5,50,0,1,0,0,0', height=20.0,
        parent_component='DisplayComponent', text='Threshold',
        width=117.0, x=10.0, y=270.0)
    scene40 = DisplayLabelModel(
        font_size=10, height=27.0, keys=[
            f'{deviceId}.imageThreshold'], parent_component='DisplayComponent',
        width=71.0, x=150.0, y=300.0)
    scene41 = CheckBoxModel(
        height=30.0, keys=[
            f'{deviceId}.subtractImagePedestal'],
        parent_component='DisplayComponent',
        width=71.0, x=150.0, y=327.0)
    scene42 = DisplayLabelModel(
        font_size=10, height=28.0, keys=[
            f'{deviceId}.thresholdType'], parent_component='DisplayComponent',
        width=71.0, x=150.0, y=357.0)
    scene43 = DisplayLabelModel(
        font_size=10, height=27.0, keys=[
            f'{deviceId}.pixelThreshold'],
        parent_component='DisplayComponent',
        width=71.0, x=150.0, y=385.0)
    scene4 = BoxLayoutModel(
        direction=2, height=112.0, width=71.0,
        x=150.0, y=300.0, children=[scene40, scene41, scene42, scene43])
    scene50 = ComboBoxModel(
        height=26.0, keys=[f'{deviceId}.thresholdType'],
        klass='EditableComboBox',
        parent_component='EditableApplyLaterComponent',
        width=81.0, x=220.0, y=360.0)
    scene51 = DoubleLineEditModel(
        height=26.0, keys=[
            f'{deviceId}.pixelThreshold'],
        parent_component='EditableApplyLaterComponent',
        width=81.0, x=220.0, y=386.0)
    scene5 = BoxLayoutModel(
        direction=2, height=52.0, width=81.0,
        x=220.0, y=360.0, children=[scene50, scene51])
    scene6 = LabelModel(
        font='Source Sans Pro,11,-1,5,50,0,1,0,0,0', height=20.0,
        parent_component='DisplayComponent', text='Fit Parameters',
        width=117.0, x=340.0, y=90.0)
    scene700 = LabelModel(
        font=default_font, foreground='#000000',
        height=25.0,
        parent_component='DisplayComponent', text='Success', width=111.0,
        x=340.0, y=120.0)
    scene701 = LabelModel(
        font=default_font, foreground='#000000',
        height=25.0,
        parent_component='DisplayComponent', text='Max Pixel Value',
        width=111.0, x=340.0, y=145.0)
    scene702 = LabelModel(
        font=default_font, foreground='#000000',
        height=25.0,
        parent_component='DisplayComponent', text='Amplitude X',
        width=111.0, x=340.0, y=170.0)
    scene703 = LabelModel(
        font=default_font, foreground='#000000',
        height=25.0,
        parent_component='DisplayComponent', text='Amplitude Y',
        width=111.0, x=340.0, y=195.0)
    scene704 = LabelModel(
        font=default_font, foreground='#000000',
        height=25.0,
        parent_component='DisplayComponent', text='Position X',
        width=111.0, x=340.0, y=220.0)
    scene705 = LabelModel(
        font=default_font, foreground='#000000',
        height=26.0,
        parent_component='DisplayComponent', text='Position Y',
        width=111.0, x=340.0, y=245.0)
    scene706 = LabelModel(
        font=default_font, foreground='#000000',
        height=25.0,
        parent_component='DisplayComponent', text='Sigma X',
        width=111.0, x=340.0, y=271.0)
    scene707 = LabelModel(
        font=default_font, foreground='#000000',
        height=25.0,
        parent_component='DisplayComponent', text='Sigma Y',
        width=111.0, x=340.0, y=296.0)
    scene708 = LabelModel(
        font=default_font, foreground='#000000',
        height=25.0,
        parent_component='DisplayComponent', text='FWHM X', width=111.0,
        x=340.0, y=321.0)
    scene709 = LabelModel(
        font=default_font, foreground='#000000',
        height=25.0,
        parent_component='DisplayComponent', text='FWHM Y',
        width=111.0, x=340.0, y=346.0)
    scene70 = BoxLayoutModel(
        direction=2, height=251.0, width=111.0, x=340.0, y=120.0, children=[
            scene700, scene701, scene702, scene703, scene704, scene705,
            scene706, scene707, scene708, scene709])
    scene710 = ErrorBoolModel(
        height=25.0, keys=[
            f'{deviceId}.success'], parent_component='DisplayComponent',
        width=110.0, x=451.0, y=120.0)
    scene711 = DisplayLabelModel(
        font_size=10, height=25.0, keys=[
            f'{deviceId}.maxPxValue'], parent_component='DisplayComponent',
        width=110.0, x=451.0, y=145.0)
    scene712 = DisplayLabelModel(
        font_size=10, height=25.0, keys=[
            f'{deviceId}.amplitudeX'], parent_component='DisplayComponent',
        width=110.0, x=451.0, y=170.0)
    scene713 = DisplayLabelModel(
        font_size=10, height=25.0, keys=[
            f'{deviceId}.amplitudeY'], parent_component='DisplayComponent',
        width=110.0, x=451.0, y=195.0)
    scene714 = DisplayLabelModel(
        font_size=10, height=25.0, keys=[
            f'{deviceId}.positionX'], parent_component='DisplayComponent',
        width=110.0, x=451.0, y=220.0)
    scene715 = DisplayLabelModel(
        font_size=10, height=26.0, keys=[
            f'{deviceId}.positionY'], parent_component='DisplayComponent',
        width=110.0, x=451.0, y=245.0)
    scene716 = DisplayLabelModel(
        font_size=10, height=25.0, keys=[
            f'{deviceId}.sigmaX'], parent_component='DisplayComponent',
        width=110.0, x=451.0, y=271.0)
    scene717 = DisplayLabelModel(
        font_size=10, height=25.0, keys=[
            f'{deviceId}.sigmaY'], parent_component='DisplayComponent',
        width=110.0, x=451.0, y=296.0)
    scene718 = DisplayLabelModel(
        font_size=10, height=25.0, keys=[
            f'{deviceId}.fwhmX'], parent_component='DisplayComponent',
        width=110.0, x=451.0, y=321.0)
    scene719 = DisplayLabelModel(
        font_size=10, height=25.0, keys=[
            f'{deviceId}.fwhmY'], parent_component='DisplayComponent',
        width=110.0, x=451.0, y=346.0)
    scene71 = BoxLayoutModel(
        direction=2, height=251.0, width=110.0, x=451.0, y=120.0, children=[
            scene710, scene711, scene712, scene713, scene714, scene715,
            scene716, scene717, scene718, scene719])
    scene7 = BoxLayoutModel(
        height=251.0, width=221.0,
        x=340.0, y=120.0, children=[scene70, scene71])
    scene8 = LineModel(
        stroke='#000000', stroke_width=2.0,
        x=320.0, x1=320.0, x2=320.0, y=80.0, y1=80.0, y2=580.0)
    scene9 = ScatterGraphModel(
        height=401.0, keys=[
            f'{deviceId}.positionX', f'{deviceId}.positionY'],
        parent_component='DisplayComponent', width=427.0, x=580.0, y=50.0)
    scene10 = LabelModel(
        font='Source Sans Pro,11,-1,5,75,0,0,0,0,0', height=20.0,
        parent_component='DisplayComponent', text='Position (Fit)',
        width=202.0, x=760.0, y=20.0)
    scene11 = TrendGraphModel(
        height=251.0, keys=[
            f'{deviceId}.positionX'], parent_component='DisplayComponent',
        width=491.0, x=1030.0, y=50.0)
    scene12 = LabelModel(
        font='Source Sans Pro,11,-1,5,75,0,0,0,0,0', height=27.0,
        parent_component='DisplayComponent', text='Position (X)',
        width=101.0, x=1240.0, y=20.0)
    scene13 = TrendGraphModel(
        height=251.0, keys=[
            f'{deviceId}.positionY'], parent_component='DisplayComponent',
        width=491.0, x=1030.0, y=350.0)
    scene14 = LabelModel(
        font='Source Sans Pro,11,-1,5,75,0,0,0,0,0', height=27.0,
        parent_component='DisplayComponent', text='Position (Y)',
        width=101.0, x=1240.0, y=320.0)
    scene15 = StickerModel(
        background='#bdbdbd', font=default_font,
        foreground='#000000', height=51.0, parent_component='DisplayComponent',
        text='Set a pixelSize for an appropriate FWHM calculation. The device defaults to `None`!',  # noqa
        width=301.0, x=10.0, y=430.0)
    scene160 = LabelModel(
        font=default_font, foreground='#000000',
        height=31.0,
        parent_component='DisplayComponent', text='Pixel Size', width=100.0,
        x=10.0, y=490.0)
    scene161 = DisplayLabelModel(
        font_size=10, height=31.0, keys=[
            f'{deviceId}.pixelSize'], parent_component='DisplayComponent',
        width=101.0, x=110.0, y=490.0)
    scene162 = DoubleLineEditModel(
        height=31.0, keys=[
            f'{deviceId}.pixelSize'],
        parent_component='EditableApplyLaterComponent',
        width=100.0, x=211.0, y=490.0)
    scene16 = BoxLayoutModel(
        height=31.0, width=301.0, x=10.0, y=490.0, children=[
            scene160, scene161, scene162])
    scene1700 = LabelModel(
        font=default_font, foreground='#000000',
        height=26.0, parent_component='DisplayComponent', text='DeviceID',
        width=67.0, x=10.0, y=20.0)
    scene1701 = LabelModel(
        font=default_font, foreground='#000000',
        height=25.0, parent_component='DisplayComponent', text='State',
        width=67.0, x=10.0, y=46.0)
    scene170 = BoxLayoutModel(
        direction=2, height=51.0, width=67.0,
        x=10.0, y=20.0, children=[scene1700, scene1701])
    scene1710 = DisplayLabelModel(
        font_size=10, height=26.0, keys=[
            f'{deviceId}.deviceId'], parent_component='DisplayComponent',
        width=304.0, x=77.0, y=20.0)
    scene1711 = DisplayStateColorModel(
        height=25.0, keys=[
            f'{deviceId}.state'], parent_component='DisplayComponent',
        show_string=True, width=304.0, x=77.0, y=46.0)
    scene171 = BoxLayoutModel(
        direction=2, height=51.0, width=304.0,
        x=77.0, y=20.0, children=[scene1710, scene1711])
    scene17 = BoxLayoutModel(
        height=51.0, width=371.0,
        x=10.0, y=20.0, children=[scene170, scene171])
    scene = SceneModel(
        height=621.0, width=1537.0, children=[
            scene0, scene1, scene2, scene3, scene4, scene5,
            scene6, scene7, scene8, scene9, scene10, scene11,
            scene12, scene13, scene14, scene15, scene16, scene17])
    return write_scene(scene)
