#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on April  6, 2016
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################
import math
import time

from karabo.bound import (
    KARABO_CLASSINFO, PythonDevice,
    BOOL_ELEMENT, DOUBLE_ELEMENT, FLOAT_ELEMENT, IMAGEDATA_ELEMENT,
    INPUT_CHANNEL, INT32_ELEMENT, OVERWRITE_ELEMENT, SLOT_ELEMENT,
    Hash, MetricPrefix, Schema, State, Unit)

from image_processing import image_processing


@KARABO_CLASSINFO("SimpleImageProcessor", "2.2")
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
                .description("The pixel size.")
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

            # Image processing outputs

            BOOL_ELEMENT(expected).key("success")
                .displayedName("Success")
                .description("Success boolean whether the image processing "
                             "was succesful or not")
                .readOnly().initialValue(False)
                .commit(),

            DOUBLE_ELEMENT(expected).key("maxPxValue")
                .displayedName("Max Pixel Value")
                .description("Maximun pixel value.")
                .unit(Unit.NUMBER)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("amplitudeX")
                .displayedName("Amplitude X")
                .description("Amplitude X from Gaussian fitting.")
                .unit(Unit.NUMBER)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("amplitudeY")
                .displayedName("Amplitude Y")
                .description("Amplitude Y from Gaussian fitting.")
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
                .description("Beam position Y from Gaussian fitting.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("sigmaX")
                .displayedName("Sigma X")
                .description("Standard deviation X from Gaussian fitting.")
                .unit(Unit.PIXEL)
                .expertAccess()
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("sigmaY")
                .displayedName("Sigma Y")
                .description("Standard deviation Y from Gaussian fitting.")
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
                .description("Uncertainty on position X from Gaussian "
                             "fitting.")
                .expertAccess()
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("errPositionY")
                .displayedName("Error Position Y")
                .description("Uncertainty on position Y from Gaussian "
                             "fitting.")
                .expertAccess()
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("errSigmaX")
                .displayedName("Error Sigma X")
                .description("Uncertainty of the standard deviation X from "
                             "Gaussian fitting.")
                .expertAccess()
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("errSigmaY")
                .displayedName("Error Sigma Y")
                .description("Uncertainty of the standard deviation Y from "
                             "Gaussian fitting.")
                .expertAccess()
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),
        )

    def initialization(self):
        """ This method will be called after the constructor. """
        self.reset()

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

        # Register call-backs
        self.KARABO_ON_DATA("input", self.onData)
        self.KARABO_ON_EOS("input", self.onEndOfStream)

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

        # ------------------------------------------------
        # 1-D Gaussian Fits

        # ------------------------------------------------
        # X Fitting
        imgX = image_processing.imageSumAlongY(img)

        # Initial parameters
        p0 = image_processing.peakParametersEval(imgX)

        # 1-d Gaussian fit
        out = image_processing.fitGauss(imgX, p0)
        paramX = out[0]  # parameters
        covX = out[1]  # covariance
        successX = out[2]  # error

        # Save fit's parameters
        self.amplitudeX = paramX[0]
        self.positionX = paramX[1]
        self.sigmaX = paramX[2]

        # ------------------------------------------------
        # Y Fitting
        imgY = image_processing.imageSumAlongX(img)

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
