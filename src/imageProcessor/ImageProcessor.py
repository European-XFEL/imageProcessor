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
    BOOL_ELEMENT, DaqDataType, DOUBLE_ELEMENT, FLOAT_ELEMENT, Hash,
    INPUT_CHANNEL, INT32_ELEMENT, KARABO_CLASSINFO, MetricPrefix,
    NODE_ELEMENT, OUTPUT_CHANNEL, OVERWRITE_ELEMENT, PythonDevice, Schema,
    SLOT_ELEMENT, State, STRING_ELEMENT, Timestamp, Unit,
    VECTOR_DOUBLE_ELEMENT, VECTOR_INT32_ELEMENT, VECTOR_STRING_ELEMENT
)

from image_processing import image_processing

from processing_utils.rate_calculator import RateCalculator


class Average():
    counter = 0
    valueSum = 0.

    def append(self, value):
        self.valueSum += value
        self.counter += 1

    def clear(self):
        self.counter = 0
        self.valueSum = 0.

    def mean(self):
        return (self.valueSum / self.counter) if self.counter > 0 else np.nan

    def __len__(self):
        return self.counter


@KARABO_CLASSINFO("ImageProcessor", "2.1")
class ImageProcessor(PythonDevice):
    # Numerical factor to convert gaussian standard deviation to beam size
    stdDev2BeamSize = 4.0
    __gaussFwhmConst = 2 * math.sqrt(2 * math.log(2))
    _averagingTimeItervall = 1.0

    @staticmethod
    def expectedParameters(expected):
        inputData = Schema()
        outputData = Schema()
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

            SLOT_ELEMENT(expected).key("useAsBackgroundImage")
                .displayedName("Current Image as Background")
                .description("Use the current image as background image.")
                .commit(),

            INPUT_CHANNEL(expected).key("input")
                .displayedName("Input")
                .dataSchema(inputData)
                .commit(),

            # Images should be dropped if processor is too slow
            OVERWRITE_ELEMENT(expected).key("input.onSlowness")
                .setNewDefaultValue("drop")
                .commit(),

            # General Settings

            BOOL_ELEMENT(expected).key("filterImagesByThreshold")
                .displayedName("Filter Images by Threshold")
                .description("If True, images will be only processed if "
                             "maximum pixel value exceeds user's defined "
                             "threshold.")
                .assignmentOptional().defaultValue(False)
                .reconfigurable()
                .commit(),

            FLOAT_ELEMENT(expected).key("imageThreshold")
                .displayedName("Image Threshold")
                .description("The threshold for processing an image.")
                .assignmentOptional().defaultValue(0.)
                .minInc(0.)
                .unit(Unit.NUMBER)
                .reconfigurable()
                .commit(),

            BOOL_ELEMENT(expected).key("absolutePositions")
                .displayedName("Peak Absolute Position")
                .description("If True, the centre-of-mass and fit results "
                             "will take into account the current settings "
                             "for ROI and binning.")
                .assignmentOptional().defaultValue(True)
                .reconfigurable()
                .commit(),

            BOOL_ELEMENT(expected).key("subtractBkgImage")
                .displayedName("Subtract Background Image")
                .description("Subtract the loaded background image.")
                .assignmentOptional().defaultValue(False)
                .reconfigurable()
                .commit(),

            BOOL_ELEMENT(expected).key("subtractImagePedestal")
                .displayedName("Subtract Image Pedestal")
                .description("Subtract the image pedestal (ie image = image "
                             "- image.min()). This is done after background "
                             "subtraction.")
                .assignmentOptional().defaultValue(True)
                .reconfigurable()
                .commit(),

            # Enabling Features

            BOOL_ELEMENT(expected).key("doMinMaxMean")
                .displayedName("Min/Max/Mean")
                .description("Get the following information from the pixels: "
                             "min, max, mean value.")
                .assignmentOptional().defaultValue(True)
                .reconfigurable()
                .commit(),

            BOOL_ELEMENT(expected).key("doBinCount")
                .displayedName("Pixel Value Frequency")
                .description("Calculate the frequency distribution of pixel "
                             "values.")
                .assignmentOptional().defaultValue(False)
                .reconfigurable()
                .commit(),

            BOOL_ELEMENT(expected).key("doXYSum")
                .displayedName("Integrate along Axes")
                .description("Integrate the image along the x- and y-axes.")
                .assignmentOptional().defaultValue(False)
                .reconfigurable()
                .commit(),

            BOOL_ELEMENT(expected).key("doCOfM")
                .displayedName("Centre-Of-Mass")
                .description("Calculate centre-of-mass and widths.")
                .assignmentOptional().defaultValue(True)
                .reconfigurable()
                .commit(),

            BOOL_ELEMENT(expected).key("do1DFit")
                .displayedName("1D Gaussian Fits")
                .description("Perform a 1D gaussian fit of the x- and "
                             "y-distributions.")
                .assignmentOptional().defaultValue(True)
                .reconfigurable()
                .commit(),

            BOOL_ELEMENT(expected).key("do2DFit")
                .displayedName("2D Gaussian Fit")
                .description("Perform a 2D gaussian fits."
                             "Be careful: It can be slow!")
                .assignmentOptional().defaultValue(False)
                .reconfigurable()
                .commit(),

            BOOL_ELEMENT(expected).key("doIntegration")
                .displayedName("Region Integration")
                .description("Perform integration over region.")
                .assignmentOptional().defaultValue(False)
                .reconfigurable()
                .commit(),

            # Options for Centre-of-Mass

            STRING_ELEMENT(expected).key("comRange")
                .displayedName("Centre-of-Mass Range")
                .description("The range to be used for the centre-of-mass "
                             "calculation. Can be the full range, or a "
                             "user-defined one.")
                .assignmentOptional().defaultValue("full")
                .options("full user-defined")
                .reconfigurable()
                .commit(),

            VECTOR_INT32_ELEMENT(expected).key("userDefinedRange")
                .displayedName("User Defined Range")
                .description("The user-defined range for centre-of-mass, "
                             "gaussian fit(s) and integrals along the x & y "
                             "axes."
                             " Region [lowX, highX) x [lowY, highY)"
                             " specified as [lowX, highX, lowY, highY]")
                .assignmentOptional().defaultValue([0, 400, 0, 400])
                .minSize(4).maxSize(4)
                .reconfigurable()
                .commit(),

            FLOAT_ELEMENT(expected).key("absThreshold")
                .displayedName("Pixel Absolute threshold")
                .description("Pixels below this threshold will not be "
                             "used for the centre-of-mass calculation. "
                             "If greater than 0, the relative threshold "
                             "will not be used.")
                .assignmentOptional().defaultValue(0.0)
                .minInc(0.0)
                .reconfigurable()
                .commit(),

            FLOAT_ELEMENT(expected).key("threshold")
                .displayedName("Pixel Relative threshold")
                .description("Pixels below this relative threshold "
                             "(fraction of the highest value) will not be "
                             "used for the centre-of-mass calculation. "
                             "It will only be applied if no absolute "
                             "threshold is set.")
                .assignmentOptional().defaultValue(0.10)
                .minInc(0.0).maxInc(1.0)
                .reconfigurable()
                .commit(),

            # Options for Gaussian Fit

            FLOAT_ELEMENT(expected).key("pixelSize")
                .displayedName("Pixel Size")
                .description("The pixel size. It will be used when evaluating "
                             "the beam size.")
                .assignmentOptional().defaultValue(0.)
                .minInc(0.)
                .unit(Unit.METER).metricPrefix(MetricPrefix.MICRO)
                .reconfigurable()
                .commit(),

            STRING_ELEMENT(expected).key("fitRange")
                .displayedName("Fit Range")
                .description("The range to be used for fitting. Can be the "
                             "full range, an auto-determined, or the "
                             "user-defined one.")
                .assignmentOptional().defaultValue("auto")
                .options("full auto user-defined")
                .reconfigurable()
                .commit(),

            FLOAT_ELEMENT(expected).key("rangeForAuto")
                .displayedName("Range for Auto")
                .description("The automatic range for 'auto' mode (in "
                             "standard deviations).")
                .assignmentOptional().defaultValue(3.0)
                .minInc(0.)
                .reconfigurable()
                .commit(),

            # userDefinedRange can be found in Centre-of-Mass section

            BOOL_ELEMENT(expected).key("enablePolynomial")
                .displayedName("Polynomial Gaussian Fits")
                .description("Add a 1st order polynomial term (ramp) to "
                             "gaussian fits.")
                .assignmentOptional().defaultValue(False)
                .reconfigurable()
                .commit(),

            STRING_ELEMENT(expected).key("gauss1dStartValues")
                .displayedName("1D gauss fit start values")
                .description("Selects how 1D gauss fit starting values are "
                             "evaluated")
                .options("last_fit_result,raw_peak")
                .assignmentOptional().defaultValue("last_fit_result")
                .reconfigurable()
                .commit(),

            BOOL_ELEMENT(expected).key("doGaussRotation")
                .displayedName("Allow Gaussian Rotation")
                .description("Allow the 2D gaussian to be rotated.")
                .assignmentOptional().defaultValue(False)
                .reconfigurable()
                .commit(),

            # Options for Integration

            VECTOR_INT32_ELEMENT(expected).key("integrationRegion")
                .displayedName("Integration Region")
                .description("The region to be integrated over.  Region "
                             "[lowX, highX) x [lowY, highY)"
                             " specified as [lowX, highX, lowY, highY]")
                .assignmentOptional().defaultValue([0, 400, 0, 400])
                .minSize(4).maxSize(4)
                .reconfigurable()
                .commit(),

            # Output - General Properties

            DOUBLE_ELEMENT(expected).key("frameRate")
                .displayedName("Frame Rate")
                .description("The actual frame rate. "
                             "It is refreshed once per second.")
                .unit(Unit.HERTZ)
                .readOnly()
                .commit(),

            INT32_ELEMENT(expected).key("imageWidth")
                .displayedName("Image Width")
                .description("The width of the incoming image.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            INT32_ELEMENT(expected).key("imageOffsetX")
                .displayedName("Image Offset X")
                .description("If the incoming image has a ROI, this "
                             "represents the X position of the top-left "
                             "corner.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            INT32_ELEMENT(expected).key("imageBinningX")
                .displayedName("Image Binning X")
                .description("The image binning in the X direction.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            INT32_ELEMENT(expected).key("imageHeight")
                .displayedName("Image Height")
                .description("The height of the incoming image.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            INT32_ELEMENT(expected).key("imageOffsetY")
                .displayedName("Image Offset Y")
                .description("If the incoming image has a ROI, this "
                             "represents the Y position of the top-left "
                             "corner.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            INT32_ELEMENT(expected).key("imageBinningY")
                .displayedName("Image Binning Y")
                .description("The image binning in the Y direction.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("minPxValue")
                .displayedName("Min Px Value")
                .description("The minimum image pixel value.")
                .unit(Unit.NUMBER)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("maxPxValue")
                .displayedName("Max Pixel Value")
                .description("The maximum image pixel value.")
                .unit(Unit.NUMBER)
                .readOnly()
            # As pixels are usually UINT16, default alarmHigh will never fire
                .alarmHigh(65536).needsAcknowledging(False)
                .commit(),

            DOUBLE_ELEMENT(expected).key("meanPxValue")
                .displayedName("Mean Pixel Value")
                .description("The mean image pixel value.")
                .unit(Unit.NUMBER)
                .readOnly()
            # As pixels are usually UINT16, default alarmHigh will never fire
                .alarmHigh(65536).needsAcknowledging(False)
                .commit(),

            # Image processing times

            FLOAT_ELEMENT(expected).key("minMaxMeanTime")
                .displayedName("Min/Max/Mean Evaluation Time")
                .description("Time spent for evaluating min, max, mean "
                             "pixel value.")
                .unit(Unit.SECOND)
                .readOnly()
                .commit(),

            FLOAT_ELEMENT(expected).key("binCountTime")
                .displayedName("Pixel Value Frequency Time")
                .description("Time spent for calculating the frequency "
                             "distribution of pixel values.")
                .unit(Unit.SECOND)
                .readOnly()
                .commit(),

            FLOAT_ELEMENT(expected).key("subtractBkgImageTime")
                .displayedName("Background Image Subtraction Time")
                .description("Time spent in subtracting the background image.")
                .unit(Unit.SECOND)
                .readOnly()
                .commit(),

            FLOAT_ELEMENT(expected).key("subtractPedestalTime")
                .displayedName("Pedestal Subtraction Time")
                .description("Time spent in subtracting the image pedestal.")
                .unit(Unit.SECOND)
                .readOnly()
                .commit(),

            FLOAT_ELEMENT(expected).key("xYSumTime")
                .displayedName("Image X-Y Integration Time")
                .description("Time spent in integrating the image in X and Y.")
                .unit(Unit.SECOND)
                .readOnly()
                .commit(),

            FLOAT_ELEMENT(expected).key("cOfMTime")
                .displayedName("Centre-Of-Mass Time")
                .description("Time spent in evaluating the centre-of-mass.")
                .unit(Unit.SECOND)
                .readOnly()
                .commit(),

            FLOAT_ELEMENT(expected).key("xFitTime")
                .displayedName("1D Gaussian Fit Time (X)")
                .description("Time spent in 1D Gaussian fit of the X "
                             "distribution.")
                .unit(Unit.SECOND)
                .readOnly()
                .commit(),

            FLOAT_ELEMENT(expected).key("yFitTime")
                .displayedName("1D Gaussian Fit Time (Y)")
                .description("Time spent in 1D Gaussian fit of the Y "
                             "distribution.")
                .unit(Unit.SECOND)
                .readOnly()
                .commit(),

            FLOAT_ELEMENT(expected).key("fitTime")
                .displayedName("2D Gaussian Fit Time")
                .description("Time spent in 2D Gaussian fit of the image.")
                .unit(Unit.SECOND)
                .readOnly()
                .commit(),

            FLOAT_ELEMENT(expected).key("integrationTime")
                .displayedName("Region Integration Time")
                .description("Time spent in integrating over a region.")
                .unit(Unit.SECOND)
                .readOnly()
                .commit(),

            # Output - Centre-of-Mass

            DOUBLE_ELEMENT(expected).key("x0")
                .displayedName("x0 (Centre-Of-Mass)")
                .description("X position of the centre-of-mass.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("sx")
                .displayedName("sigma_x (Centre-Of-Mass)")
                .description("Standard deviation in X of the centre-of-mass.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("y0")
                .displayedName("y0 (Centre-Of-Mass)")
                .description("Y position of the centre-of-mass.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("sy")
                .displayedName("sigma_y (Centre-Of-Mass)")
                .description("Standard deviation in Y of the centre-of-mass.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            # Output - Gaussian Fit (1D)

            INT32_ELEMENT(expected).key("xFitSuccess")
                .displayedName("x Success (1D Fit)")
                .description("1D Gaussian fit success (1-4 if fit "
                             "converged).")
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("ax1d")
                .displayedName("Ax (1D Fit)")
                .description("Amplitude Ax from the 1D fit.")
                .unit(Unit.NUMBER)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("x01d")
                .displayedName("x0 (1D Fit)")
                .description("x0 peak position from 1D fit.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("ex01d")
                .displayedName("sigma(x0) (1D Fit)")
                .description("Uncertainty on x0 estimation.")
                .expertAccess()
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("sx1d")
                .displayedName("sigma_x (1D Fit)")
                .description("Standard deviation on x0 from 1D fit.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("esx1d")
                .displayedName("sigma(sigma_x) (1D Fit)")
                .description("Uncertainty on standard deviation estimation.")
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
                .description("1D Gaussian Fit Success (1-4 if fit "
                             "converged).")
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("ay1d")
                .displayedName("Ay (1D Fit)")
                .description("Amplitude Ay from 1D fit.")
                .unit(Unit.NUMBER)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("y01d")
                .displayedName("y0 (1D Fit)")
                .description("y0 peak position from 1D fit.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("ey01d")
                .displayedName("sigma(y0) (1D Fit)")
                .description("Uncertainty on y0 estimation.")
                .expertAccess()
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("sy1d")
                .displayedName("sigma_y (1D Fit)")
                .description("Standard deviation on y0 from 1D fit.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("esy1d")
                .displayedName("sigma(sigma_y) (1D Fit)")
                .description("Uncertainty on standard deviation estimation.")
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

            # Output - Gaussian Fit (2D)

            INT32_ELEMENT(expected).key("fitSuccess")
                .displayedName("Success (2D Fit)")
                .description("2D Gaussian fit success (1-4 if fit "
                             "converged).")
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("a2d")
                .displayedName("A (2D Fit)")
                .description("Amplitude from 2D fit.")
                .unit(Unit.NUMBER)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("x02d")
                .displayedName("x0 (2D Fit)")
                .description("x0 peak position from 2D fit.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("ex02d")
                .displayedName("sigma(x0) (2D Fit)")
                .description("Uncertainty on x0 estimation.")
                .expertAccess()
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("sx2d")
                .displayedName("sigma_x (2D Fit)")
                .description("Standard deviation on x0 from 2D fit.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("esx2d")
                .displayedName("sigma(sigma_x) (2D Fit)")
                .description("Uncertainty on standard deviation estimation.")
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
                .description("y0 peak position from 2D fit.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("ey02d")
                .displayedName("sigma(y0) (2D Fit)")
                .description("Uncertainty on y0 estimation.")
                .expertAccess()
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("sy2d")
                .displayedName("sigma_y (2D Fit)")
                .description("Standard deviation on y0 from 2D fit.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("esy2d")
                .displayedName("sigma(sigma_y) (2D Fit)")
                .description("Uncertainty on standard deviation estimation.")
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
                .description("Rotation angle from 2D fit.")
                .unit(Unit.RADIAN)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("etheta2d")
                .displayedName("sigma(theta) (2D Fit)")
                .description("Uncertainty on rotation angle estimation.")
                .expertAccess()
                .unit(Unit.RADIAN)
                .readOnly()
                .commit(),

            # Output - integration

            DOUBLE_ELEMENT(expected).key("regionIntegral")
                .displayedName("Integral Over Region")
                .description("Integral of pixel value over region "
                             "specified by integrationRegion.")
                .unit(Unit.NUMBER)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected).key("regionMean")
                .displayedName("Mean Over Region")
                .description("Mean pixel value over region "
                             "specified by integrationRegion.")
                .unit(Unit.NUMBER)
                .readOnly()
                .commit(),

            # Other outputs

            NODE_ELEMENT(outputData).key("data")
                .displayedName("Data")
                .setDaqDataType(DaqDataType.TRAIN)
                .commit(),

            VECTOR_INT32_ELEMENT(outputData).key("data.imgBinCount")
                .displayedName("Pixel counts distribution")
                .description("Distribution of the image pixel counts.")
                .unit(Unit.NUMBER)
                .readOnly().initialValue([0])
                .commit(),

            VECTOR_DOUBLE_ELEMENT(outputData).key("data.imgX")
                .displayedName("X Distribution")
                .description("Image integral along the Y-axis.")
                .readOnly().initialValue([0])
                .commit(),

            VECTOR_DOUBLE_ELEMENT(outputData).key("data.imgY")
                .displayedName("Y Distribution")
                .description("Image integral along the X-axis.")
                .readOnly().initialValue([0])
                .commit(),

            OUTPUT_CHANNEL(expected).key("output")
                .displayedName("Output")
                .dataSchema(outputData)
                .commit(),

        )

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

        # Define good range for gaussian fit
        self.xMin = None
        self.xMax = None
        self.yMin = None
        self.yMax = None

        # Current image
        self.currentImage = None

        # Background image
        self.bkgImage = None

        # Register additional slots
        self.registerSlot(self.reset)
        self.registerSlot(self.useAsBackgroundImage)
        # TODO: save/load bkg image slots

        # Processing time averages
        self.lastUpdateTime = time.time()
        self.averagers = {'minMaxMeanTime': Average(),
                          'binCountTime': Average(),
                          'subtractBkgImageTime': Average(),
                          'subtractPedestalTime': Average(),
                          'xYSumTime': Average(),
                          'cOfMTime': Average(),
                          'xFitTime': Average(),
                          'yFitTime': Average(),
                          'fitTime': Average(),
                          'integrationTime': Average()
                          }

        # Register call-backs
        self.KARABO_ON_DATA("input", self.onData)
        self.KARABO_ON_EOS("input", self.onEndOfStream)

        self.registerInitialFunction(self.initialization)

        # Variables for frames per second computation
        self.frame_rate = RateCalculator(refresh_interval=1.0)

    def initialization(self):
        """ This method will be called after the constructor. """
        self.reset()

    def useAsBackgroundImage(self):
        self.log.INFO("Use current image as background.")
        # Copy current image to background image
        self.bkgImage = np.array(self.currentImage)

    def reset(self):
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
        h.set("integrationTime", 0.0)

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
        h.set("regionIntegral", 0.0)
        h.set("regionMean", 0.0)

        h.set("frameRate", 0.)

        # Reset device parameters (all at once)
        self.set(h)

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

            if firstImage:
                # Update warning levels
                dims = imageData.getDimensions()
                imageHeight = dims[0]
                imageWidth = dims[1]
                self.updateWarnLevels(0, imageWidth, 0, imageHeight)

                bpp = imageData.getBitsPerPixel()
                self.updateOutputSchema(imageHeight, imageWidth, bpp)

            ts = Timestamp.fromHashAttributes(
                metaData.getAttributes('timestamp'))
            self.processImage(imageData, ts)  # Process image

        except Exception as e:
            self.log.ERROR("Exception caught in onData: %s" % str(e))

    def onEndOfStream(self, inputChannel):
        self.log.INFO("End of Stream")
        self.set("frameRate", 0.)
        # Signals end of stream
        self.signalEndOfStream("output")
        self.updateState(State.ON)

    def processImage(self, imageData, ts):
        filterImagesByThreshold = self.get("filterImagesByThreshold")
        imageThreshold = self.get("imageThreshold")
        comRange = self.get("comRange")
        fitRange = self.get("fitRange")
        sigmas = self.get("rangeForAuto")
        absThr = self.get("absThreshold")
        thr = self.get("threshold")
        userDefinedRange = self.get("userDefinedRange")
        absolutePositions = self.get("absolutePositions")

        h = Hash()  # Device properties updates
        outHash = Hash()  # Output channel updates

        self.refreshFrameRate()

        try:
            pixelSize = self.get("pixelSize")
        except:
            # No pixel size
            pixelSize = None

        try:
            dims = imageData.getDimensions()
            imageHeight = dims[0]
            imageWidth = dims[1]
            if imageWidth != self.get("imageWidth"):
                h.set("imageWidth", imageWidth)
            if imageHeight != self.get("imageHeight"):
                h.set("imageHeight", imageHeight)

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
                imageBinning = imageData.getBinning()
                imageBinningY = imageBinning[0]
                imageBinningX = imageBinning[1]
                if imageBinningX != self.get("imageBinningX"):
                    h.set("imageBinningX", imageBinningX)
                if imageBinningY != self.get("imageBinningY"):
                    h.set("imageBinningY", imageBinningY)
            except:
                # Image has no binning information
                imageBinningY = 1
                imageBinningX = 1

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
            self.averagers["minMaxMeanTime"].append(t1 - t0)

            h.set("minPxValue", float(imgMin))
            h.set("maxPxValue", float(imgMax))
            h.set("meanPxValue", float(imgMean))
            self.log.DEBUG("Pixel min/max/mean: done!")
        else:
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
            self.averagers["binCountTime"].append(t1 - t0)

            outHash.set("data.imgBinCount", pxFreq.tolist())
        else:
            outHash.set("data.imgBinCount", [0])

        # Background image subtraction
        if self.get("subtractBkgImage"):
            t0 = time.time()
            try:
                if(self.bkgImage is not None and
                   self.bkgImage.shape == img.shape):

                    if self.currentImage is img:
                        # Must copy, or self.currentImage will be modified
                        self.currentImage = img.copy()

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
            self.averagers["subtractBkgImageTime"].append(t1 - t0)
            self.log.DEBUG("Background image subtraction: done!")

        # Pedestal subtraction
        if self.get("subtractImagePedestal"):  # was "doBackground"
            t0 = time.time()
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

            t1 = time.time()
            self.averagers["subtractPedestalTime"].append(t1 - t0)
            self.log.DEBUG("Image pedestal subtraction: done!")

        # Sum the image along the x- and y-axes
        imgX = None
        imgY = None
        if self.get("doXYSum"):
            t0 = time.time()
            try:
                xmin = np.maximum(userDefinedRange[0], 0)
                xmax = np.minimum(userDefinedRange[1], imageWidth)
                ymin = np.maximum(userDefinedRange[2], 0)
                ymax = np.minimum(userDefinedRange[3], imageHeight)
                data = img[ymin:ymax, xmin:xmax]
                # Sums along Y- and X-axes
                imgX = image_processing.imageSumAlongY(data)
                imgY = image_processing.imageSumAlongX(data)

            except Exception as e:
                self.log.WARN("Could not sum image along x or y axis: %s." %
                              str(e))
                return

            if imgX is None or imgY is None:
                self.log.WARN("Could not sum image along x or y axis.")
                return

            t1 = time.time()
            self.averagers["xYSumTime"].append(t1 - t0)

            outHash.set("data.imgX", imgX.astype(np.float).tolist())
            outHash.set("data.imgY", imgY.astype(np.float).tolist())
            self.log.DEBUG("Image X-Y sums: done!")
        else:
            outHash.set("data.imgX", [0.0])
            outHash.set("data.imgY", [0.0])

        # Centre-of-Mass and widths
        x0 = None
        y0 = None
        sx = None
        sy = None
        if self.get("doCOfM") or self.get("do1DFit") or self.get("do2DFit"):

            t0 = time.time()
            try:
                # Set a threshold to cut away noise
                if absThr > 0.0:
                    img2 = img.copy()
                    image_processing.\
                        imageSetThreshold(img2, min(absThr, img2.max()))
                else:
                    img2 = img.copy()
                    image_processing.\
                        imageSetThreshold(img2, thr * img2.max())

                # Centre-of-Mass and widths
                if comRange == "user-defined":
                    img3 = img2[userDefinedRange[2]:userDefinedRange[3],
                                userDefinedRange[0]:userDefinedRange[1]]
                    (x0, y0, sx, sy) = image_processing.imageCentreOfMass(img3)
                    x0 += userDefinedRange[0]
                    y0 += userDefinedRange[2]
                else:  # "full"
                    (x0, y0, sx, sy) = image_processing.imageCentreOfMass(img2)

                if fitRange == "full":
                    xmin = 0
                    xmax = imageWidth
                    ymin = 0
                    ymax = imageHeight
                elif fitRange == "user-defined":
                    xmin = np.maximum(userDefinedRange[0], 0)
                    xmax = np.minimum(userDefinedRange[1], imageWidth)
                    ymin = np.maximum(userDefinedRange[2], 0)
                    ymax = np.minimum(userDefinedRange[3], imageHeight)
                    # TODO check that xmin<xmax and ymin<ymax
                else:  # "auto"
                    xmin = np.maximum(int(x0 - sigmas * sx), 0)
                    xmax = np.minimum(int(x0 + sigmas * sx), imageWidth)
                    ymin = np.maximum(int(y0 - sigmas * sy), 0)
                    ymax = np.minimum(int(y0 + sigmas * sy), imageHeight)

            except Exception as e:
                self.log.WARN("Could not calculate centre-of-mass: %s." %
                              str(e))
                return

            t1 = time.time()
            self.averagers["cOfMTime"].append(t1 - t0)

            if absolutePositions:
                h.set("x0", imageBinningX*(x0 + imageOffsetX))
                h.set("y0", imageBinningY*(y0 + imageOffsetY))
            else:
                h.set("x0", x0)
                h.set("y0", y0)
            h.set("sx", sx)
            h.set("sy", sy)
            self.log.DEBUG("Centre-of-mass and widths: done!")

        else:
            h.set("x0", 0.0)
            h.set("sx", 0.0)
            h.set("y0", 0.0)
            h.set("sx", 0.0)

        # 1D Gaussian Fits
        if self.get("do1DFit"):

            enable_polynomial = self.get("enablePolynomial")
            gauss1dStartValues = self.get("gauss1dStartValues")

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
                if gauss1dStartValues == "raw_peak":
                    # evaluate peak parameters w/o fit
                    p0 = self.evalStartingPoint(data)
                elif gauss1dStartValues == "last_fit_result":
                    if None not in (self.ax1d, self.x01d, self.sx1d):
                        # Use last fit's parameters as initial estimate
                        p0 = (self.ax1d, self.x01d - xmin, self.sx1d)
                    elif None not in (x0, sx):
                        # Use CoM for initial parameter estimate
                        p0 = (data.max(), x0 - xmin, sx)
                    else:
                        # No initial parameters
                        p0 = None
                        # TODO "p0 = self.evalStartingPoint(data)" may be used
                        # as well, once it's well tested
                else:
                    raise RuntimeError("unexpected gauss1dStartValues option")

                # 1D gaussian fit
                out = image_processing.fitGauss(
                    data, p0, enablePolynomial=enable_polynomial)
                pX = out[0]  # parameters
                cX = out[1]  # covariance
                successX = out[2]  # error

                # Save fit's parameters
                self.ax1d, self.x01d, self.sx1d = pX[0], pX[1] + xmin, pX[2]

            except Exception as e:
                self.log.WARN("Could not do 1D gaussian fit [x]: %s." %
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
                if gauss1dStartValues == "raw_peak":
                    # evaluate peak parameters w/o fit
                    p0 = self.evalStartingPoint(data)
                elif gauss1dStartValues == "last_fit_result":
                    if None not in (self.ay1d, self.y01d, self.sy1d):
                        # Use last fit's parameters as initial estimate
                        p0 = (self.ay1d, self.y01d - ymin, self.sy1d)
                    elif None not in (y0, sy):
                        # Use CoM for initial parameter estimate
                        p0 = (data.max(), y0 - ymin, sy)
                    else:
                        # No initial parameters
                        p0 = None
                        # TODO "p0 = self.evalStartingPoint(data)" may be used
                        # as well, once it's well tested
                else:
                    raise RuntimeError("unexpected gauss1dStartValues option")

                # 1D gaussian fit
                out = image_processing.fitGauss(
                    data, p0, enablePolynomial=enable_polynomial)
                pY = out[0]  # parameters
                cY = out[1]  # covariance
                successY = out[2]  # error

                # Save fit's parameters
                self.ay1d, self.y01d, self.sy1d = pY[0], pY[1] + ymin, pY[2]

            except Exception as e:
                self.log.WARN("Could not do 1D gaussian fit [y]: %s." %
                              str(e))
                return

            t2 = time.time()
            self.averagers["xFitTime"].append(t1 - t0)
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
                        h.set("x01d",
                              imageBinningX*(xmin + pX[1] + imageOffsetX))
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

            self.averagers["yFitTime"].append(t2 - t1)
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
                        h.set("y01d",
                              imageBinningY*(ymin + pY[1] + imageOffsetY))
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

            self.log.DEBUG("1D gaussian fit: done!")
        else:
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

        # 2D Gaussian Fits
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

                    # 2D gaussian fit
                    out = image_processing.fitGauss2DRot(
                        data, p0, enablePolynomial=enable_polynomial)
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

                    # 2D gaussian fit
                    out = image_processing.fitGauss(
                        data, p0, enablePolynomial=enable_polynomial)
                    pXY = out[0]  # parameters: A, x0, y0, sx, sy
                    cXY = out[1]  # covariance
                    successXY = out[2]  # error

                    # Save fit's parameters
                    self.a2d, self.x02d, self.y02d, self.sx2d, self.sy2d = (
                        pXY[0], pXY[1] + xmin, pXY[2] + ymin, pXY[3], pXY[4])

            except Exception as e:
                self.log.WARN("Could not do 2D gaussian fit: %s." % str(e))
                return

            t1 = time.time()

            self.averagers["fitTime"].append(t1 - t0)
            h.set("fitSuccess", successXY)

            if successXY in (1, 2, 3, 4):
                # Successful fit
                h.set("a2d", pXY[0])

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
                    h.set("x02d",
                          imageBinningX*(xmin + pXY[1] + imageOffsetX))
                    h.set("y02d",
                          imageBinningY*(ymin + pXY[2] + imageOffsetY))
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
                    h.set("theta2d", pXY[5] % (2. * math.pi))
                    if cXY is not None:
                        h.set("etheta2d", math.sqrt(cXY[5][5]))
                else:
                    h.set("theta2d", 0.0)
                    h.set("etheta2d", 0.0)

            self.log.DEBUG("2D gaussian fit: done!")
        else:
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

        # Region Integration
        integrationDone = False
        if self.get("doIntegration"):
            try:
                t0 = time.time()
                integrationRegion = self.get("integrationRegion")
                xmin = np.maximum(integrationRegion[0], 0)
                xmax = np.minimum(integrationRegion[1], imageWidth)
                ymin = np.maximum(integrationRegion[2], 0)
                ymax = np.minimum(integrationRegion[3], imageHeight)
                data = img[ymin:ymax, xmin:xmax]
                integral = np.float64(np.sum(data))
                h.set("regionIntegral", integral)
                regionMean = integral / data.size if data.size > 0 else 0.0
                h.set("regionMean", regionMean)
                t1 = time.time()
                self.averagers["integrationTime"].append(t1 - t0)
                integrationDone = True
                self.log.DEBUG("Region integration: done!")
            except Exception as e:
                self.log.WARN("Could not do integration: %s." % str(e))
        if not integrationDone:
            h.set("regionIntegral", 0.0)
            h.set("regionMean", 0.0)

        if time.time() - self.lastUpdateTime > self._averagingTimeItervall:
            # average processing times over 1 second
            for key, averager in self.averagers.items():
                if averager:
                    h.set(key, averager.mean())
                    averager.clear()

            self.lastUpdateTime = time.time()

        # Update device parameters (all at once)
        self.set(h, ts)
        self.writeChannel("output", outHash, ts)

    def evalStartingPoint(self, data):
        fitAmpl, peakPixel, fwhm = image_processing.peakParametersEval(data)

        return (fitAmpl, peakPixel, fwhm/self.__gaussFwhmConst)

    def updateWarnLevels(self, xMin, xMax, yMin, yMax):
        newSchema = Schema()
        needsUpdate = False

        if xMin != self.xMin or xMax != self.xMax:
            (
                DOUBLE_ELEMENT(newSchema).key("x01d")
                    .displayedName("x0 (1D Fit)")
                    .description("x0 from 1D Fit.")
                    .unit(Unit.PIXEL)
                    .readOnly()
                    .warnLow(xMin).needsAcknowledging(False)
                    .warnHigh(xMax).needsAcknowledging(False)
                    .commit(),

                DOUBLE_ELEMENT(newSchema).key("x02d")
                    .displayedName("x0 (2D Fit)")
                    .description("x0 from 2D Fit.")
                    .unit(Unit.PIXEL)
                    .readOnly()
                    .warnLow(xMin).needsAcknowledging(False)
                    .warnHigh(xMax).needsAcknowledging(False)
                    .commit(),
            )
            self.xMin = xMin
            self.xMax = xMax
            needsUpdate = True

        if yMin != self.yMin or yMax != self.yMax:
            (
                DOUBLE_ELEMENT(newSchema).key("y01d")
                    .displayedName("y0 (1D Fit)")
                    .description("y0 from 1D Fit.")
                    .unit(Unit.PIXEL)
                    .readOnly()
                    .warnLow(yMin).needsAcknowledging(False)
                    .warnHigh(yMax).needsAcknowledging(False)
                    .commit(),

                DOUBLE_ELEMENT(newSchema).key("y02d")
                    .displayedName("y0 (2D Fit)")
                    .description("y0 from 2D Fit.")
                    .unit(Unit.PIXEL)
                    .readOnly()
                    .warnLow(yMin).needsAcknowledging(False)
                    .warnHigh(yMax).needsAcknowledging(False)
                    .commit(),
            )
            self.yMin = yMin
            self.yMax = yMax
            needsUpdate = True

        if needsUpdate:
            self.updateSchema(newSchema)

    def updateOutputSchema(self, width, height, bpp):
        # Get device configuration before schema update
        try:
            outputHostname = self["output.hostname"]
        except AttributeError as e:
            # Configuration does not contain "output.hostname"
            outputHostname = None

        newSchema = Schema()
        outputData = Schema()
        (
            NODE_ELEMENT(outputData).key("data")
                .displayedName("Data")
                .setDaqDataType(DaqDataType.TRAIN)
                .commit(),

            VECTOR_INT32_ELEMENT(outputData).key("data.imgBinCount")
                .displayedName("Pixel counts distribution")
                .description("Distribution of the image pixel counts.")
                .unit(Unit.NUMBER)
                .maxSize(min(65535, 2**bpp))
                .readOnly().initialValue([0])
                .commit(),

            VECTOR_DOUBLE_ELEMENT(outputData).key("data.imgX")
                .displayedName("X Distribution")
                .description("Image sum along the Y-axis.")
                .maxSize(width)
                .readOnly().initialValue([0])
                .commit(),

            VECTOR_DOUBLE_ELEMENT(outputData).key("data.imgY")
                .displayedName("Y Distribution")
                .description("Image sum along the X-axis.")
                .maxSize(height)
                .readOnly().initialValue([0])
                .commit(),

            OUTPUT_CHANNEL(newSchema).key("output")
                .displayedName("Output")
                .dataSchema(outputData)
                .commit(),
        )

        self.updateSchema(newSchema)

        if outputHostname:
            # Restore configuration
            self.log.DEBUG("output.hostname: %s" % outputHostname)
            self.set("output.hostname", outputHostname)

    def refreshFrameRate(self):
        self.frame_rate.update()
        fps = self.frame_rate.refresh()
        if fps:
            self['frameRate'] = fps
            self.log.DEBUG('Input rate %f Hz' % fps)
