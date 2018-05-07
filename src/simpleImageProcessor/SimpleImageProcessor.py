#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on April  6, 2016
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

import numpy as np
import time

from karabo.bound import (
    KARABO_CLASSINFO, PythonDevice,
    BOOL_ELEMENT, DOUBLE_ELEMENT, FLOAT_ELEMENT, IMAGEDATA_ELEMENT,
    INPUT_CHANNEL, INT32_ELEMENT, OVERWRITE_ELEMENT, SLOT_ELEMENT,
    Hash, MetricPrefix, Schema, State, Unit
)

from image_processing import image_processing


@KARABO_CLASSINFO("SimpleImageProcessor", "2.2")
class SimpleImageProcessor(PythonDevice):
    # Numerical factor to convert gaussian standard deviation to beam size
    std_to_fwhm = 2.35

    @staticmethod
    def expectedParameters(expected):
        data = Schema()
        (
            OVERWRITE_ELEMENT(expected).key("state")
                .setNewOptions(State.ON, State.ACQUIRING)
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

            INT32_ELEMENT(expected).key("imageOffsetX")
                .displayedName("Image Offset X")
                .description("The image offset in X direction, i.e. the X "
                             "position of its top-left corner.")
                .adminAccess()
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            INT32_ELEMENT(expected).key("imageOffsetY")
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
                .assignmentOptional().defaultValue(1.0)
                .unit(Unit.METER).metricPrefix(MetricPrefix.MICRO)
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

            FLOAT_ELEMENT(expected).key("fitRange")
                .displayedName("Fit Range")
                .description("The range for the gaussian fit (in standard "
                             "deviations).")
                .assignmentOptional().defaultValue(3.0)
                .expertAccess()
                .init()
                .commit(),

            FLOAT_ELEMENT(expected).key("pixelThreshold")
                .displayedName("Pixel Relative threshold")
                .description("The pixel threshold for centre-of-gravity "
                             "calculation (fraction of highest value). Pixels "
                             "below threshold will be discarded.")
                .assignmentOptional().defaultValue(0.10)
                .minInc(0.0).maxInc(1.0)
                .expertAccess()
                .init()
                .commit(),

            BOOL_ELEMENT(expected).key("subtractImagePedestal")
                .displayedName("Subtract Image Pedestal")
                .description("Subtract the image pedestal (ie image = image - "
                             "image.min()) before centre-of-mass and gaussian "
                             "fit.")
                .assignmentOptional().defaultValue(True)
                .expertAccess()
                .init()
                .commit(),

            # Image processing outputs

            DOUBLE_ELEMENT(expected).key("maxPxValue")
                .displayedName("Max Pixel Value")
                .description("Maximun pixel value.")
                .unit(Unit.NUMBER)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("amplitudeX")
                .displayedName("Amplitude X")
                .description("Amplitude X from gaussian fitting.")
                .unit(Unit.NUMBER)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("amplitudeY")
                .displayedName("Amplitude Y")
                .description("Amplitude Y from gaussian fitting.")
                .unit(Unit.NUMBER)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("centerX")
                .displayedName("Center X")
                .description("Center X from gaussian fitting.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("centerY")
                .displayedName("Center Y")
                .description("Center Y from gaussian fitting.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("sigmaX")
                .displayedName("Sigma X")
                .description("SigmaX from gaussian fitting.")
                .unit(Unit.PIXEL)
                .expertAccess()
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("sigmaY")
                .displayedName("Sigma Y")
                .description("Sigma Y from gaussian fitting.")
                .unit(Unit.PIXEL)
                .expertAccess()
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("fwhmX")
                .displayedName("FWHM X")
                .description("FWHM obtained from sigma.")
                .unit(Unit.METER).metricPrefix(MetricPrefix.MICRO)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("fwhmY")
                .displayedName("FWHM Y")
                .description("FWHM obtained from sigmaY.")
                .unit(Unit.METER).metricPrefix(MetricPrefix.MICRO)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("errCenterX")
                .displayedName("Error Center X")
                .description("Uncertainty on center X from gaussian fitting.")
                .expertAccess()
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("errCenterY")
                .displayedName("Error Center Y")
                .description("Uncertainty on centerY from gaussian fitting.")
                .expertAccess()
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("errSigmaX")
                .displayedName("Error Sigma X")
                .description("Uncertainty on sigma_x from gaussian fitting.")
                .expertAccess()
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("errSigmaY")
                .displayedName("Error Sigma Y")
                .description("Uncertainty on sigmaY from gaussian fitting.")
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

        # 1d gaussian fit parameters
        self.amplitudeX = None
        self.centerX = None
        self.sigmaX = None
        self.amplitudeY = None
        self.centerY = None
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
        h.set("centerX", 0.0)
        h.set("errCenterX", 0.0)
        h.set("sigmaX", 0.0)
        h.set("errSigmaX", 0.0)
        h.set("fwhmX", 0.0)
        h.set("amplitudeY", 0.0)
        h.set("centerY", 0.0)
        h.set("errCenterY", 0.0)
        h.set("sigmaY", 0.0)
        h.set("errSigmaY", 0.0)
        h.set("fwhmY", 0.0)

        # Reset device parameters (all at once)
        self.set(h)

    def onData(self, data, metaData):
        if self.get("state") == State.ON:
            self.log.INFO("Start of Stream")
            self.updateState(State.ACQUIRING)
        try:
            if data.has('data.image'):
                self.processImage(data['data.image'])
            elif data.has('image'):
                # To ensure backward compatibility
                # with older versions of cameras
                self.processImage(data['image'])
            else:
                self.log.INFO("data does not have any image")
        except Exception as e:
            self.log.ERROR("Exception caught in onData: %s" % str(e))

    def onEndOfStream(self, inputChannel):
        self.log.INFO("End of Stream")
        self.set("frameRate", 0.)
        self.updateState(State.ON)

    def processImage(self, imageData):
        imgThr = self.get("imageThreshold")
        fitRange = self.get("fitRange")
        pxThr = self.get("pixelThreshold")

        h = Hash()  # Empty hash

        try:
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
        except Exception as e:
            self.log.ERROR("Exception caught in processImage: %s" % str(e))

        try:
            pixelSize = self.get("pixelSize")
        except:
            # No pixel size, using default
            pixelSize = 1.

        try:
            dims = imageData.getDimensions()
            imageSizeY = dims[0]
            imageSizeX = dims[1]
            if imageSizeX != self.get("imageSizeX"):
                h.set("imageSizeX", imageSizeX)
            if imageSizeY != self.get("imageSizeY"):
                h.set("imageSizeY", imageSizeY)

            try:
                roiOffsets = imageData.getROIOffsets()
                imageOffsetY = roiOffsets[0]
                imageOffsetX = roiOffsets[1]
            except:
                # Image has no ROI offset
                imageOffsetX = 0
                imageOffsetY = 0
            if imageOffsetX != self.get("imageOffsetX"):
                h.set("imageOffsetX", imageOffsetX)
            if imageOffsetY != self.get("imageOffsetY"):
                h.set("imageOffsetY", imageOffsetY)

            try:
                binning = imageData.getBinning()
                binningY = binning[0]
                binningX = binning[1]
                if binningX != self.get("binningX"):
                    h.set("binningX", binningX)
                if binningY != self.get("binningY"):
                    h.set("binningY", binningY)
            except:
                # Image has no binning information
                binningY = 1
                binningX = 1

            self.currentImage = imageData.getData()  # np.ndarray
            img = self.currentImage  # Shallow copy
            if img.ndim == 3 and img.shape[2] == 1:
                # Image has 3rd dimension (channel), but it's 1
                self.log.DEBUG("Reshaping image...")
                img = img.squeeze()

            self.log.DEBUG("Image loaded!!!")

        except Exception as e:
            self.log.WARN("In processImage: %s" % str(e))
            return

        # Filter by Threshold
        if img.max() < imgThr:
            self.log.DEBUG("Max pixel value below threshold: image "
                           "discarded!!!")
            return

        # Get pixel max value
        try:
            imgMax = img.max()
            h.set("maxPxValue", float(imgMax))
        except Exception as e:
            self.log.WARN("Could not read pixel max: %s." % str(e))
            return

        self.log.DEBUG("Pixel max: done!")

        # Pedestal subtraction
        if self.get("subtractImagePedestal"):
            try:
                imgMin = img.min()
                if imgMin > 0:
                    if self.currentImage is img:
                        # Must copy, or self.currentImage will be modified
                        self.currentImage = img.copy()

                    # Subtract image pedestal
                    img -= imgMin
            except Exception as e:
                self.log.WARN("Could not subtract image pedestal: %s." %
                              str(e))
                return

            self.log.DEBUG("Image pedestal subtraction: done!")

        # Centre-Of-Mass and widths
        try:
            # Set a threshold to cut away noise
            img2 = image_processing.imageSetThreshold(img, pxThr * img.max())

            # Centre-of-mass and widths
            (x0, y0, sx, sy) = image_processing.imageCentreOfMass(img2)

            xmin = np.maximum(int(x0 - fitRange * sx), 0)
            xmax = np.minimum(int(x0 + fitRange * sx), imageSizeX)
            ymin = np.maximum(int(y0 - fitRange * sy), 0)
            ymax = np.minimum(int(y0 + fitRange * sy), imageSizeY)

        except Exception as e:
            self.log.WARN("Could not calculate centre-of-mass: %s." % str(e))
            return

        self.log.DEBUG("Centre-of-mass and widths: done!")

        # 1-D Gaussian Fits
        try:
            # Sum image along y axis
            imgX = image_processing.imageSumAlongY(img)

            # Select sub-range and substract pedestal
            data = imgX[xmin:xmax]
            imgMin = data.min()
            if imgMin > 0:
                data -= data.min()

            # Initial parameters
            if None not in (self.amplitudeX, self.centerX, self.sigmaX):
                # Use last fit's parameters as initial estimate
                p0 = (self.amplitudeX, self.centerX - xmin, self.sigmaX)
            elif None not in (x0, sx):
                # Use CoM for initial parameter estimate
                p0 = (data.max(), x0 - xmin, sx)
            else:
                # No initial parameters
                p0 = None

            # 1-d gaussian fit
            out = image_processing.fitGauss(data, p0)
            pX = out[0]  # parameters
            cX = out[1]  # covariance
            successX = out[2]  # error

            # Save fit's parameters
            self.amplitudeX, self.centerX, self.sigmaX = pX[0], pX[1] + xmin, pX[2]

        except Exception as e:
            self.log.WARN("Could not do 1-d gaussian fit [x]: %s." % str(e))
            return

        try:
            # Sum image along x axis
            imgY = image_processing.imageSumAlongX(img)

            # Select sub-range and substract pedestal
            data = imgY[ymin:ymax]
            imgMin = data.min()
            if imgMin > 0:
                data -= data.min()

            # Initial parameters
            if None not in (self.amplitudeY, self.centerY, self.sigmaY):
                # Use last fit's parameters as initial estimate
                p0 = (self.amplitudeY, self.centerY - ymin, self.sigmaY)
            elif None not in (y0, sy):
                # Use CoM for initial parameter estimate
                p0 = (data.max(), y0 - ymin, sy)
            else:
                # No initial parameters
                p0 = None

            # 1-d gaussian fit
            out = image_processing.fitGauss(data, p0)
            pY = out[0]  # parameters
            cY = out[1]  # covariance
            successY = out[2]  # error

            # Save fit's parameters
            self.amplitudeY = pY[0]
            self.centerY = pY[1] + ymin
            self.sigmaY = pY[2]

        except Exception as e:
            self.log.WARN("Could not do 1-d gaussian fit [y]: %s." % str(e))
            return

        if successX in (1, 2, 3, 4):
            # Successful fit
            h.set("centerX",
                  binningX * (xmin + pX[1] + imageOffsetX))
            errCenterX = np.sqrt(cX[1][1])
            h.set("errCenterX", errCenterX)
            h.set("sigmaX", pX[2])
            errSigmaX = np.sqrt(cX[2][2])
            h.set("errSigmaX", errSigmaX)
            if pixelSize is not None:
                fwhmX = self.std_to_fwhm * pixelSize * pX[2]
                h.set("fwhmX", fwhmX)

        if successY in (1, 2, 3, 4):
            # Successful fit
            h.set("centerY",
                  binningY * (ymin + pY[1] + imageOffsetY))
            errCenterY = np.sqrt(cY[1][1])
            h.set("errCenterY", errCenterY)
            h.set("sigmaY", pY[2])
            errSigmaY = np.sqrt(cY[2][2])
            h.set("errSigmaY", errSigmaY)
            if pixelSize is not None:
                fwhmY = self.std_to_fwhm * pixelSize * pY[2]
                h.set("fwhmY", fwhmY)

        if successX in (1, 2, 3, 4) and successY in (1, 2, 3, 4):
            amplitudeX = pX[0] / pY[2] / np.sqrt(2 * np.pi)
            amplitudeY = pY[0] / pX[2] / np.sqrt(2 * np.pi)
            h.set("amplitudeX", amplitudeX)
            h.set("amplitudeY", amplitudeY)

        self.log.DEBUG("1-d gaussian fit: done!")

        # Update device parameters (all at once)
        self.set(h)
