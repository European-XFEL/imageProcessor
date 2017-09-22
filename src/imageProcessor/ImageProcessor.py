#!/usr/bin/env python

# TODO: display 1d and 2d fits

#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on October 10, 2013
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

import math
import numpy as np
import time

from karabo.bound import (
    KARABO_CLASSINFO, PythonDevice, launchPythonDevice, OkErrorFsm,
    BOOL_ELEMENT, DOUBLE_ELEMENT, FLOAT_ELEMENT,
    INPUT_CHANNEL, INT32_ELEMENT, OVERWRITE_ELEMENT, SLOT_ELEMENT,
    STRING_ELEMENT, VECTOR_DOUBLE_ELEMENT, VECTOR_INT32_ELEMENT,
    Hash, MetricPrefix, Schema, Unit
)

from image_processing import image_processing


@KARABO_CLASSINFO("ImageProcessor", "2.1")
class ImageProcessor(PythonDevice, OkErrorFsm):
    # Numerical factor to convert gaussian standard deviation to beam size
    stdDev2BeamSize = 4.0

    def __init__(self, configuration):
        # always call superclass constructor first!
        super(ImageProcessor, self).__init__(configuration)

        # 1d gaussian fit parameters
        self.ax1d = None
        self.x01d = None
        self.sx1d = None
        self.ay1d = None
        self.y01d = None
        self.sy1d = None

        # 2d gaussian fit parameters
        self.a2d = None
        self.x02d = None
        self.sx2d = None
        self.y02d = None
        self.sy2d = None
        self.theta2d = None

        # Current image
        self.currentImage = None

        # Background image
        self.bkgImage = None

        # frames per second
        self.lastTime = None
        self.counter = 0

        # Register additional slots
        self._ss.registerSlot(self.useAsBackgroundImage)
        # TODO: save/load bkg image slots

    def __del__(self):
        super(ImageProcessor, self).__del__()

    @staticmethod
    def expectedParameters(expected):
        data = Schema()

        (
            SLOT_ELEMENT(expected).key("useAsBackgroundImage")
                .displayedName("Current Image as Background")
                .description("Use the current image as background image.")
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

            INT32_ELEMENT(expected).key("imageWidth")
                .displayedName("Image Width")
                .description("The image width.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            INT32_ELEMENT(expected).key("imageOffsetX")
                .displayedName("Image Offset X")
                .description("The image offset in X direction, i.e. the Y "
                             "position of its top-left corner.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            INT32_ELEMENT(expected).key("imageHeight")
                .displayedName("Image Height")
                .description("The image height.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            INT32_ELEMENT(expected).key("imageOffsetY")
                .displayedName("Image Offset Y")
                .description("The image offset in Y direction, i.e. the Y "
                             "position of its top-left corner.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            FLOAT_ELEMENT(expected).key("pixelSize")
                .displayedName("Pixel Size")
                .description("The pixel size.")
                .assignmentOptional().defaultValue(0.)
                .unit(Unit.METER).metricPrefix(MetricPrefix.MICRO)
                .reconfigurable()
                .commit(),

            BOOL_ELEMENT(expected).key("filterImagesByThreshold")
                .displayedName("Filter Images by Threshold")
                .description("If True, images will be fitted only if maximum "
                             "pixel value exceeds user's defined threshold.")
                .assignmentOptional().defaultValue(False)
                .reconfigurable()
                .commit(),

            FLOAT_ELEMENT(expected).key("imageThreshold")
                .displayedName("Image Threshold")
                .description("The threshold for image fitting.")
                .assignmentOptional().defaultValue(0.)
                .unit(Unit.NUMBER)
                .reconfigurable()
                .commit(),

            STRING_ELEMENT(expected).key("fitRange")
                .displayedName("Fit Range")
                .description("The range to be used for fitting. Can be the "
                             "full image, auto-determined range, "
                             "user-defined range.")
                .assignmentOptional().defaultValue("auto")
                .options("full auto user-defined")
                .reconfigurable()
                .commit(),

            FLOAT_ELEMENT(expected).key("rangeForAuto")
                .displayedName("Range for Auto")
                .description("The range for auto mode (in standard "
                             "deviations).")
                .assignmentOptional().defaultValue(3.0)
                .reconfigurable()
                .commit(),

            VECTOR_INT32_ELEMENT(expected).key("userDefinedRange")
                .displayedName("User Defined Range")
                .description("The user-defined range for centre-of-gravity "
                             "and gaussian fit(s).")
                .assignmentOptional().defaultValue([0, 400, 0, 400])
                .reconfigurable()
                .commit(),

            BOOL_ELEMENT(expected).key("absolutePositions")
                .displayedName("Peak Absolute Position")
                .description("If True, the peak position will be w.r.t. to "
                             "the full frame, not to the ROI.")
                .assignmentOptional().defaultValue(True)
                .reconfigurable()
                .commit(),

            FLOAT_ELEMENT(expected).key("threshold")
                .displayedName("Pixel Relative threshold")
                .description("The pixel threshold for centre-of-gravity "
                             "calculation (fraction of highest value).")
                .assignmentOptional().defaultValue(0.10)
                .minInc(0.0).maxInc(1.0)
                .reconfigurable()
                .commit(),

            # Image processing enable bits

            BOOL_ELEMENT(expected).key("doMinMaxMean")
                .displayedName("Min/Max/Mean")
                .description("Get the following information from the pixels: "
                             "min, max, mean value.")
                .assignmentOptional().defaultValue(True)
                .reconfigurable()
                .commit(),

            BOOL_ELEMENT(expected).key("doBinCount")
                .displayedName("Pixel Value Frequency")
                .description("Frequency distribution of pixel values.")
                .assignmentOptional().defaultValue(False)
                .reconfigurable()
                .commit(),

            BOOL_ELEMENT(expected).key("subtractBkgImage")
                .displayedName("Subtract Background Image")
                .description("Subtract the background image.")
                .assignmentOptional().defaultValue(False)
                .reconfigurable()
                .commit(),

            BOOL_ELEMENT(expected).key("subtractImagePedestal")
                .displayedName("Subtract Image Pedestal")
                .description("Subtract the image pedestal (ie image = image "
                             "- image.min()).")
                .assignmentOptional().defaultValue(True)
                .reconfigurable()
                .commit(),

            BOOL_ELEMENT(expected).key("doXYSum")
                .displayedName("Sum along X-Y Axes")
                .description("Sum image along the x- and y-axes.")
                .assignmentOptional().defaultValue(False)
                .reconfigurable()
                .commit(),

            BOOL_ELEMENT(expected).key("doCOfM")
                .displayedName("Centre-Of-Mass")
                .description("Calculates centre-of-mass and widths.")
                .assignmentOptional().defaultValue(True)
                .reconfigurable()
                .commit(),

            BOOL_ELEMENT(expected).key("do1DFit")
                .displayedName("1-D Gaussian Fits")
                .description("Perform a 1-d gaussian fit of the x- and "
                             "y-distributions.")
                .assignmentOptional().defaultValue(True)
                .reconfigurable()
                .commit(),

            BOOL_ELEMENT(expected).key("do2DFit")
                .displayedName("2-D Gaussian Fit")
                .description("Perform a 2-d gaussian fits.")
                .assignmentOptional().defaultValue(False)
                .reconfigurable()
                .commit(),

            BOOL_ELEMENT(expected).key("doGaussRotation")
                .displayedName("Allow Gaussian Rotation")
                .description("Allow the 2D gaussian to be rotated.")
                .assignmentOptional().defaultValue(False)
                .reconfigurable()
                .commit(),

            # Image processing times

            FLOAT_ELEMENT(expected).key("minMaxMeanTime")
                .displayedName("Min/Max/Mean Evaluation Time")
                .unit(Unit.SECOND)
                .readOnly()
                .commit(),

            FLOAT_ELEMENT(expected).key("binCountTime")
                .displayedName("Pixel Value Frequency Time")
                .unit(Unit.SECOND)
                .readOnly()
                .commit(),

            FLOAT_ELEMENT(expected).key("subtractBkgImageTime")
                .displayedName("Background Image Subtraction Time")
                .unit(Unit.SECOND)
                .readOnly()
                .commit(),

            FLOAT_ELEMENT(expected).key("subtractPedestalTime")
                .displayedName("Pedestal Subtraction Time")
                .unit(Unit.SECOND)
                .readOnly()
                .commit(),

            FLOAT_ELEMENT(expected).key("xYSumTime")
                .displayedName("Image X-Y Sums Time")
                .unit(Unit.SECOND)
                .readOnly()
                .commit(),

            FLOAT_ELEMENT(expected).key("cOfMTime")
                .displayedName("Centre-Of-Mass Time")
                .unit(Unit.SECOND)
                .readOnly()
                .commit(),

            FLOAT_ELEMENT(expected).key("xFitTime")
                .displayedName("1D Gaussian Fit Time (X distribution)")
                .unit(Unit.SECOND)
                .readOnly()
                .commit(),

            FLOAT_ELEMENT(expected).key("yFitTime")
                .displayedName("1D Gaussian Fit Time (Y distribution)")
                .unit(Unit.SECOND)
                .readOnly()
                .commit(),

            FLOAT_ELEMENT(expected).key("fitTime")
                .displayedName("2D Gaussian Fit Time")
                .unit(Unit.SECOND)
                .readOnly()
                .commit(),

            # Image processing outputs

            DOUBLE_ELEMENT(expected).key("minPxValue")
                .displayedName("Min Px Value")
                .description("Minimun pixel value.")
                .unit(Unit.NUMBER)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("maxPxValue")
                .displayedName("Max Pixel Value")
                .description("Maximun pixel value.")
                .unit(Unit.NUMBER)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("meanPxValue")
                .displayedName("Mean Pixel Value")
                .description("Mean pixel value.")
                .unit(Unit.NUMBER)
                .readOnly()
                .commit(),

            VECTOR_DOUBLE_ELEMENT(expected).key("imgBinCount")
                .displayedName("Pixel counts distribution")
                .description("Distribution of the image pixel counts.")
                .unit(Unit.NUMBER)
                .readOnly().initialValue([0])
                .commit(),

            VECTOR_DOUBLE_ELEMENT(expected).key("imgX")
                .displayedName("X Distribution")
                .description("Image sum along the Y-axis.")
                .readOnly().initialValue([0])
                .commit(),

            VECTOR_DOUBLE_ELEMENT(expected).key("imgY")
                .displayedName("Y Distribution")
                .description("Image sum along the X-axis.")
                .readOnly().initialValue([0])
                .commit(),

            DOUBLE_ELEMENT(expected).key("x0")
                .displayedName("x0 (Centre-Of-Mass)")
                .description("x0 from centre-of-mass.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("sx")
                .displayedName("sigma_x (Centre-Of-Mass)")
                .description("sigma_x from centre-of-mass.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("y0")
                .displayedName("y0 (Centre-Of-Mass)")
                .description("y0 from Centre-Of-Mass.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("sy")
                .displayedName("sigma_y (Centre-Of-Mass)")
                .description("sigma_y from Centre-Of-Mass.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            INT32_ELEMENT(expected).key("xFitSuccess")
                .displayedName("x Success (1D Fit)")
                .description("1-D Gaussian Fit Success (1-4 if fit "
                             "converged).")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("ax1d")
                .displayedName("Ax (1D Fit)")
                .description("Amplitude Ax from 1D Fit.")
                .unit(Unit.NUMBER)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("x01d")
                .displayedName("x0 (1D Fit)")
                .description("x0 from 1D Fit.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("ex01d")
                .displayedName("sigma(x0) (1D Fit)")
                .description("Uncertainty on x0 from 1D Fit.")
                .expertAccess()
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("sx1d")
                .displayedName("sigma_x (1D Fit)")
                .description("sigma_x from 1D Fit.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("esx1d")
                .displayedName("sigma(sigma_x) (1D Fit)")
                .description("Uncertainty on sigma_x from 1D Fit.")
                .expertAccess()
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("beamWidth1d")
                .displayedName("Beam Width (1D Fit)")
                .description("Beam width from 1D Fit. Defined as 4x sigma_x.")
                .unit(Unit.METER).metricPrefix(MetricPrefix.MICRO)
                .readOnly()
                .commit(),

            INT32_ELEMENT(expected).key("yFitSuccess")
                .displayedName("y Success (1D Fit)")
                .description("1-D Gaussian Fit Success (1-4 if fit "
                             "converged).")
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("ay1d")
                .displayedName("Ay (1D Fit)")
                .description("Amplitude Ay from 1D Fit.")
                .unit(Unit.NUMBER)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("y01d")
                .displayedName("y0 (1D Fit)")
                .description("y0 from 1D Fit.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("ey01d")
                .displayedName("sigma(y0) (1D Fit)")
                .description("Uncertainty on y0 from 1D Fit.")
                .expertAccess()
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("sy1d")
                .displayedName("sigma_y (1D Fit)")
                .description("sigma_y from 1D Fit.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("esy1d")
                .displayedName("sigma(sigma_y) (1D Fit)")
                .description("Uncertainty on sigma_y from 1D Fit.")
                .expertAccess()
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("beamHeight1d")
                .displayedName("Beam Height (1D Fit)")
                .description("Beam heigth from 1D Fit. Defined as 4x "
                             "sigma_y.")
                .unit(Unit.METER).metricPrefix(MetricPrefix.MICRO)
                .readOnly()
                .commit(),

            INT32_ELEMENT(expected).key("fitSuccess")
                .displayedName("Success (2D Fit)")
                .description("2-D Gaussian Fit Success (1-4 if fit "
                             "converged).")
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("a2d")
                .displayedName("A (2D Fit)")
                .description("Amplitude A from 2D Fit.")
                .unit(Unit.NUMBER)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("x02d")
                .displayedName("x0 (2D Fit)")
                .description("x0 from 2D Fit.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("ex02d")
                .displayedName("sigma(x0) (2D Fit)")
                .description("Uncertainty on x0 from 2D Fit.")
                .expertAccess()
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("sx2d")
                .displayedName("sigma_x (2D Fit)")
                .description("sigma_x from 2D Fit.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("esx2d")
                .displayedName("sigma(sigma_x) (2D Fit)")
                .description("Uncertainty on sigma_x from 2D Fit.")
                .expertAccess()
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("beamWidth2d")
                .displayedName("Beam Width (2D Fit)")
                .description("Beam width from 2D Fit. Defined as 4x sigma_x.")
                .unit(Unit.METER).metricPrefix(MetricPrefix.MICRO)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("y02d")
                .displayedName("y0 (2D Fit)")
                .description("y0 from 2D Fit.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("ey02d")
                .displayedName("sigma(y0) (2D Fit)")
                .description("Uncertainty on y0 from 2D Fit.")
                .expertAccess()
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("sy2d")
                .displayedName("sigma_y (2D Fit)")
                .description("sigma_y from 2D Fit.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("esy2d")
                .displayedName("sigma(sigma_y) (2D Fit)")
                .description("Uncertainty on sigma_y from 2D Fit.")
                .expertAccess()
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("beamHeight2d")
                .displayedName("Beam Height (2D Fit)")
                .description("Beam height from 2D Fit. Defined as 4x sigma_y.")
                .unit(Unit.METER).metricPrefix(MetricPrefix.MICRO)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("theta2d")
                .displayedName("theta (2D Fit)")
                .description("Rotation angle from 2D Fit.")
                .unit(Unit.DEGREE)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("etheta2d")
                .displayedName("sigma(theta) (2D Fit)")
                .description("Uncertianty on rotation angle from 2D Fit.")
                .expertAccess()
                .unit(Unit.DEGREE)
                .readOnly()
                .commit(),
        )

    ##############################################
    #   Implementation of State Machine methods  #
    ##############################################

    def useAsBackgroundImage(self):
        self.log.INFO("Use current image as background.")
        # Copy current image to background image
        self.bkgImage = np.array(self.currentImage)

    def okStateOnEntry(self):

        # Register call-backs
        self.KARABO_ON_DATA("input", self.onData)
        self.KARABO_ON_EOS("input", self.onEndOfStream)

        h = Hash()

        h.set("minMaxMeanTime", 0.0)
        h.set("binCountTime", 0.0)
        h.set("subtractBkgImageTime", 0.0)
        h.set("subtractPedestalTime", 0.0)
        h.set("xYSumTime", 0.0)
        h.set("cOfMTime", 0.0)
        h.set("xFitTime", 0.0)
        h.set("yFitTime", 0.0)
        h.set("fitTime", 0.0)

        h.set("minPxValue", 0.0)
        h.set("maxPxValue", 0.0)
        h.set("meanPxValue", 0.0)
        h.set("x0", 0.0)
        h.set("sx", 0.0)
        h.set("y0", 0.0)
        h.set("sy", 0.0)
        h.set("xFitSuccess", 0)
        h.set("ax1d", 0.0)
        h.set("x01d", 0.0)
        h.set("ex01d", 0.0)
        h.set("sx1d", 0.0)
        h.set("esx1d", 0.0)
        h.set("beamWidth1d", 0.0)
        h.set("yFitSuccess", 0)
        h.set("ay1d", 0.0)
        h.set("y01d", 0.0)
        h.set("sy1d", 0.0)
        h.set("beamHeight1d", 0.0)
        h.set("fitSuccess", 0)
        h.set("a2d", 0.0)
        h.set("x02d", 0.0)
        h.set("ex02d", 0.0)
        h.set("sx2d", 0.0)
        h.set("esx2d", 0.0)
        h.set("beamWidth2d", 0.0)
        h.set("y02d", 0.0)
        h.set("ey02d", 0.0)
        h.set("sy2d", 0.0)
        h.set("esy2d", 0.0)
        h.set("theta2d", 0.0)
        h.set("etheta2d", 0.0)
        h.set("beamHeight2d", 0.0)

        # Reset device parameters (all at once)
        self.set(h)

    def onData(self, data, metaData):
        try:
            if data.has('data.image'):
                self.processImage(data['data.image'])
            elif data.has('image'):
                # To ensure backward compatibility
                # with older versions of cameras
                self.processImage(data['image'])
            else:
                self.log.DEBUG("data does not have any image")
        except Exception as e:
            self.log.ERROR("Exception caught in onData: %s" % str(e))

    def onEndOfStream(self):
        self.log.INFO("onEndOfStream called")

    def processImage(self, imageData):
        filterImagesByThreshold = self.get("filterImagesByThreshold")
        imageThreshold = self.get("imageThreshold")
        range = self.get("fitRange")
        sigmas = self.get("rangeForAuto")
        thr = self.get("threshold")
        userDefinedRange = self.get("userDefinedRange")
        absolutePositions = self.get("absolutePositions")

        h = Hash()  # Empty hash

        try:
            self.counter += 1
            currentTime = time.time()
            if self.lastTime is None:
                self.counter = 0
                self.lastTime = currentTime
            elif (self.lastTime is not None and
                  (currentTime - self.lastTime) > 1.):
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
            # No pixel size
            pixelSize = None

        try:
            dims = imageData.getDimensions()
            imageHeight = dims[0]
            imageWidth = dims[1]
            h.set("imageWidth", imageWidth)
            h.set("imageHeight", imageHeight)

            try:
                roiOffsets = imageData.getROIOffsets()
                imageOffsetY = roiOffsets[0]
                imageOffsetX = roiOffsets[1]
            except:
                # Image has no ROI offset
                imageOffsetX = 0
                imageOffsetY = 0
            h.set("imageOffsetX", imageOffsetX)
            h.set("imageOffsetY", imageOffsetY)

            img = imageData.getData()  # np.ndarray
            if img.ndim == 3 and img.shape[2] == 1:
                # Image has 3rd dimension (channel), but it's 1
                self.log.DEBUG("Reshaping image...")
                img = img.squeeze()

            # Copy current image, before doing any processing
            self.currentImage = np.array(img)
            self.log.DEBUG("Image loaded!!!")

        except Exception as e:
            self.log.WARN("In processImage: %s" % str(e))
            return

        # Filter by Threshold
        if filterImagesByThreshold:
            if img.max() < imageThreshold:
                self.log.DEBUG("Max pixel value below threshold: image "
                               "discared!!!")
                return

        # Get pixel min/max/mean values
        if self.get("doMinMaxMean"):
            t0 = time.time()
            try:
                imgMin = img.min()
                imgMax = img.max()
                imgMean = img.mean()
            except Exception as e:
                self.log.WARN("Could not read min, max, mean: %s." % str(e))
                return

            t1 = time.time()

            h.set("minMaxMeanTime", (t1 - t0))
            h.set("minPxValue", float(imgMin))
            h.set("maxPxValue", float(imgMax))
            h.set("meanPxValue", float(imgMean))
            self.log.DEBUG("Pixel min/max/mean: done!")
        else:
            h.set("minMaxMeanTime", 0.0)
            h.set("minPxValue", 0.0)
            h.set("maxPxValue", 0.0)
            h.set("meanPxValue", 0.0)

        # Frequency of Pixel Values
        if self.get("doBinCount"):
            t0 = time.time()
            try:
                pxFreq = image_processing.imagePixelValueFrequencies(img)

                self.log.DEBUG("Pixel values distribution: done!")
            except Exception as e:
                self.log.WARN("Could not evaluate the pixel value frequency:"
                              " %s." % str(e))
                return

            t1 = time.time()

            h.set("binCountTime", (t1 - t0))
            h.set("imgBinCount", pxFreq.tolist())
        else:
            h.set("binCountTime", 0.0)
            h.set("imgBinCount", [0.0])

        # Background image subtraction
        if self.get("subtractBkgImage"):
            t0 = time.time()
            try:
                if(self.bkgImage is not None and
                   self.bkgImage.shape == img.shape):
                    # Subtract background image
                    m = (img > self.bkgImage)  # img is above bkg
                    n = (img <= self.bkgImage)  # image is below bkg

                    # subtract bkg from img, where img is above bkg
                    img[m] -= self.bkgImage[m]
                    img[n] = 0  # zero img, where its is below bkg

            except Exception as e:
                self.log.WARN("Could not subtract background image: %s." %
                              str(e))
                return

            t1 = time.time()

            h.set("subtractBkgImageTime", (t1 - t0))
            self.log.DEBUG("Background image subtraction: done!")
        else:
            h.set("subtractBkgImageTime", 0.0)

        # Pedestal subtraction
        if self.get("subtractImagePedestal"):  # was "doBackground"
            t0 = time.time()
            try:
                imgMin = img.min()
                if imgMin > 0:
                    # Subtract image pedestal
                    img = img - imgMin
            except Exception as e:
                self.log.WARN("Could not subtract image pedestal: %s." %
                              str(e))
                return

            t1 = time.time()

            h.set("subtractPedestalTime", (t1 - t0))  # was "backgroundTime"
            self.log.DEBUG("Image pedestal subtraction: done!")
        else:
            h.set("subtractPedestalTime", 0.0)  # was "backgroundTime"

        # Sum the image along the x- and y-axes
        imgX = None
        imgY = None
        if self.get("doXYSum"):
            t0 = time.time()
            try:
                imgX = image_processing.imageSumAlongY(img)  # sum along y axis
                imgY = image_processing.imageSumAlongX(img)  # sum along x axis

            except Exception as e:
                self.log.WARN("Could not sum image along x or y axis: %s." %
                              str(e))
                return

            if imgX is None or imgY is None:
                self.log.WARN("Could not sum image along x or y axis.")
                return

            t1 = time.time()

            h.set("xYSumTime", (t1 - t0))
            h.set("imgX", imgX.tolist())
            h.set("imgY", imgY.tolist())
            self.log.DEBUG("Image X-Y sums: done!")
        else:
            h.set("xYSumTime", 0.0)
            h.set("imgX", [0.0])
            h.set("imgY", [0.0])

        # Centre-Of-Mass and widths
        x0 = None
        y0 = None
        sx = None
        sy = None
        if self.get("doCOfM") or self.get("do1DFit") or self.get("do2DFit"):

            t0 = time.time()
            try:
                # Set a threshold to cut away noise
                img2 = image_processing.imageSetThreshold(img, thr * img.max())

                # Centre-of-mass and widths
                (x0, y0, sx, sy) = image_processing.imageCentreOfMass(img2)

                if range == "full":
                    xmin = 0
                    xmax = imageWidth
                    ymin = 0
                    ymax = imageHeight
                elif range == "user-defined":
                    xmin = np.maximum(userDefinedRange[0], 0)
                    xmax = np.minimum(userDefinedRange[1], imageWidth)
                    ymin = np.maximum(userDefinedRange[2], 0)
                    ymax = np.minimum(userDefinedRange[3], imageHeight)
                    # TODO check that xmin<xmax and ymin<ymax
                else:
                    # "auto"
                    xmin = np.maximum(int(x0 - sigmas * sx), 0)
                    xmax = np.minimum(int(x0 + sigmas * sx), imageWidth)
                    ymin = np.maximum(int(y0 - sigmas * sy), 0)
                    ymax = np.minimum(int(y0 + sigmas * sy), imageHeight)

            except Exception as e:
                self.log.WARN("Could not calculate centre-of-mass: %s." %
                              str(e))
                return

            t1 = time.time()

            h.set("cOfMTime", (t1 - t0))
            if absolutePositions:
                h.set("x0", x0 + imageOffsetX)
                h.set("y0", y0 + imageOffsetY)
            else:
                h.set("x0", x0)
                h.set("y0", y0)
            h.set("sx", sx)
            h.set("sy", sy)
            self.log.DEBUG("Centre-of-mass and widths: done!")

        else:
            h.set("cOfMTime", 0.0)
            h.set("x0", 0.0)
            h.set("sx", 0.0)
            h.set("y0", 0.0)
            h.set("sx", 0.0)

        # 1-D Gaussian Fits
        if self.get("do1DFit"):

            t0 = time.time()
            try:
                if imgX is None:
                    imgX = image_processing.imageSumAlongY(img)

                # Select sub-range and substract pedestal
                data = imgX[xmin:xmax]
                imgMin = data.min()
                if imgMin > 0:
                    data -= data.min()

                # Initial parameters
                if None not in (self.ax1d, self.x01d, self.sx1d):
                    # Use last fit's parameters as initial estimate
                    p0 = (self.ax1d, self.x01d - xmin, self.sx1d)
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
                self.ax1d, self.x01d, self.sx1d = pX[0], pX[1] + xmin, pX[2]

            except Exception as e:
                self.log.WARN("Could not do 1-d gaussian fit [x]: %s." %
                              str(e))
                return

            t1 = time.time()

            try:
                if imgY is None:
                    imgY = image_processing.imageSumAlongX(img)

                # Select sub-range and substract pedestal
                data = imgY[ymin:ymax]
                imgMin = data.min()
                if imgMin > 0:
                    data -= data.min()

                # Initial parameters
                if None not in (self.ay1d, self.y01d, self.sy1d):
                    # Use last fit's parameters as initial estimate
                    p0 = (self.ay1d, self.y01d - ymin, self.sy1d)
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
                self.ay1d, self.y01d, self.sy1d = pY[0], pY[1] + ymin, pY[2]

            except Exception as e:
                self.log.WARN("Could not do 1-d gaussian fit [y]: %s." %
                              str(e))
                return

            t2 = time.time()

            h.set("xFitTime", (t1 - t0))
            h.set("xFitSuccess", successX)

            if successX in (1, 2, 3, 4):
                # Successful fit
                if cX is None:
                    self.log.WARN("Successful X fit with singular covariance "
                                  "matrix. Resetting initial fit values.")
                    self.ax1d = None
                    self.x01d = None
                    self.sx1d = None
                try:
                    if absolutePositions:
                        h.set("x01d", xmin + pX[1] + imageOffsetX)
                    else:
                        h.set("x01d", xmin + pX[1])

                    if cX is not None:
                        ex01d = math.sqrt(cX[1][1])
                        esx1d = math.sqrt(cX[2][2])
                    else:
                        ex01d = 0.0
                        esx1d = 0.0

                    h.set("ex01d", ex01d)
                    h.set("esx1d", esx1d)
                    h.set("sx1d", pX[2])

                    if pixelSize is not None:
                        beamWidth = self.stdDev2BeamSize * pixelSize * pX[2]
                        h.set("beamWidth1d", beamWidth)

                except Exception as e:
                    self.log.WARN("Exception caught after successful X fit: %s"
                                  % str(e))

            h.set("yFitTime", (t2 - t1))
            h.set("yFitSuccess", successY)

            if successY in (1, 2, 3, 4):
                # Successful fit
                if cY is None:
                    self.log.WARN("Successful Y fit with singular covariance "
                                  "matrix.. Resetting initial fit values.")
                    self.ay1d = None
                    self.y01d = None
                    self.sy1d = None

                try:
                    if absolutePositions:
                        h.set("y01d", ymin + pY[1] + imageOffsetY)
                    else:
                        h.set("y01d", ymin + pY[1])

                    if cY is not None:
                        ey01d = math.sqrt(cY[1][1])
                        esy1d = math.sqrt(cY[2][2])
                    else:
                        ey01d = 0.0
                        esy1d = 0.0
                    h.set("ey01d", ey01d)
                    h.set("esy1d", esy1d)

                    h.set("sy1d", pY[2])

                    if pixelSize is not None:
                        beamHeight = self.stdDev2BeamSize * pixelSize * pY[2]
                        h.set("beamHeight1d", beamHeight)

                except Exception as e:
                    self.log.WARN("Exception caught after successful Y fit: %s"
                                  % str(e))

            if successX in (1, 2, 3, 4) and successY in (1, 2, 3, 4):
                ax1d = pX[0] / pY[2] / math.sqrt(2 * math.pi)
                ay1d = pY[0] / pX[2] / math.sqrt(2 * math.pi)
                h.set("ax1d", ax1d)
                h.set("ay1d", ay1d)

            self.log.DEBUG("1-d gaussian fit: done!")
        else:
            h.set("xFitTime", 0.0)
            h.set("yFitTime", 0.0)
            h.set("xFitSuccess", 0)
            h.set("ax1d", 0.0)
            h.set("x01d", 0.0)
            h.set("ex01d", 0.0)
            h.set("sx1d", 0.0)
            h.set("esx1d", 0.0)
            h.set("beamWidth1d", 0.0)
            h.set("yFitSuccess", 0)
            h.set("ay1d", 0.0)
            h.set("y01d", 0.0)
            h.set("sy1d", 0.0)
            h.set("beamHeight1d", 0.0)

        # 2-D Gaussian Fits
        rotation = self.get("doGaussRotation")
        if self.get("do2DFit"):
            t0 = time.time()

            try:
                # Input data
                data = img[ymin:ymax, xmin:xmax]
                imgMin = data.min()
                if imgMin > 0:
                    data -= data.min()

                if rotation:

                    # Initial parameters
                    if None not in (self.a2d, self.x02d, self.y02d,
                                    self.sx2d, self.sy2d, self.theta2d):
                        # Use last fit's parameters as initial estimate
                        p0 = (self.a2d, self.x02d - xmin, self.y02d - ymin,
                              self.sx2d, self.sy2d, self.theta2d)
                    elif None not in (x0, y0, sx, sy):
                        # Use CoM for initial parameter estimate
                        p0 = (data.max(), x0 - xmin, y0 - ymin, sx, sy, 0.0)
                    else:
                        p0 = None

                    # 2-d gaussian fit
                    out = image_processing.fitGauss2DRot(data, p0)
                    pXY = out[0]  # parameters: A, x0, y0, sx, sy, theta
                    cXY = out[1]  # covariance
                    successXY = out[2]  # error

                    # Save fit's parameters
                    self.a2d, self.x02d, self.y02d, self.sx2d, self.sy2d = (
                        pXY[0], pXY[1] + xmin, pXY[2] + ymin, pXY[3], pXY[4])
                    self.theta2d = pXY[5]

                else:

                    # Initial parameters
                    if None not in (self.a2d, self.x02d, self.y02d,
                                    self.sx2d, self.sy2d):
                        # Use last fit's parameters as initial estimate
                        p0 = (self.a2d, self.x02d - xmin, self.y02d - ymin,
                              self.sx2d, self.sy2d)
                    elif None not in (x0, y0, sx, sy):
                        # Use CoM for initial parameter estimate
                        p0 = (data.max(), x0 - xmin, y0 - ymin, sx, sy)
                    else:
                        p0 = None

                    # 2-d gaussian fit
                    out = image_processing.fitGauss(data, p0)
                    pXY = out[0]  # parameters: A, x0, y0, sx, sy
                    cXY = out[1]  # covariance
                    successXY = out[2]  # error

                    # Save fit's parameters
                    self.a2d, self.x02d, self.y02d, self.sx2d, self.sy2d = (
                        pXY[0], pXY[1] + xmin, pXY[2] + ymin, pXY[3], pXY[4])

            except Exception as e:
                self.log.WARN("Could not do 2-d gaussian fit: %s." % str(e))
                return

            t1 = time.time()

            h.set("fitTime", (t1 - t0))
            h.set("fitSuccess", successXY)
            if successXY in (1, 2, 3, 4):
                h.set("a2d", pXY[0])
                # Successful fit
                if cXY is None:
                    self.log.WARN("Successful XY fit with singular covariance "
                                  "matrix. Resetting initial fit values.")
                    self.a2d = None
                    self.x02d = None
                    self.y02d = None
                    self.sx2d = None
                    self.sy2d = None
                    if rotation:
                        self.theta2d = None

                if absolutePositions:
                    h.set("x02d", xmin + pXY[1] + imageOffsetX)
                    h.set("y02d", ymin + pXY[2] + imageOffsetY)
                else:
                    h.set("x02d", xmin + pXY[1])
                    h.set("y02d", ymin + pXY[2])

                if cXY is not None:
                    h.set("ex02d", math.sqrt(cXY[1][1]))
                    h.set("ey02d", math.sqrt(cXY[2][2]))
                    h.set("esx2d", math.sqrt(cXY[3][3]))
                    h.set("esy2d", math.sqrt(cXY[4][4]))
                else:
                    h.set("ex02d", 0.0)
                    h.set("ey02d", 0.0)
                    h.set("esx2d", 0.0)
                    h.set("esy2d", 0.0)

                h.set("sx2d", pXY[3])
                h.set("sy2d", pXY[4])

                if pixelSize is not None:
                    beamWidth = self.stdDev2BeamSize * pixelSize * pXY[3]
                    h.set("beamWidth2d", beamWidth)
                    beamHeight = self.stdDev2BeamSize * pixelSize * pXY[4]
                    h.set("beamHeight2d", beamHeight)
                if rotation:
                    h.set("theta2d", pXY[5] % math.pi)
                    if cXY is not None:
                        h.set("etheta2d", math.sqrt(cXY[5][5]))
                else:
                    h.set("theta2d", 0.0)
                    h.set("etheta2d", 0.0)

            self.log.DEBUG("2-d gaussian fit: done!")
        else:
            h.set("fitTime", 0.0)
            h.set("fitSuccess", 0)
            h.set("a2d", 0.0)
            h.set("x02d", 0.0)
            h.set("ex02d", 0.0)
            h.set("sx2d", 0.0)
            h.set("esx2d", 0.0)
            h.set("beamWidth2d", 0.0)
            h.set("y02d", 0.0)
            h.set("ey02d", 0.0)
            h.set("sy2d", 0.0)
            h.set("esy2d", 0.0)
            h.set("beamHeight2d", 0.0)
            h.set("theta2d", 0.0)
            h.set("etheta2d", 0.0)

        # Update device parameters (all at once)
        self.set(h)


if __name__ == "__main__":
    launchPythonDevice()
