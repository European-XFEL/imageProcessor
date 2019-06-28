#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on October 10, 2013
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

import math
import numpy as np
import time

from karabo.bound import (
    BOOL_ELEMENT, DaqDataType, Dims, DOUBLE_ELEMENT, FLOAT_ELEMENT, Hash,
    INT32_ELEMENT, KARABO_CLASSINFO, MetricPrefix, NODE_ELEMENT,
    OUTPUT_CHANNEL, Schema, SLOT_ELEMENT, State, STRING_ELEMENT, Timestamp,
    Unit, VECTOR_DOUBLE_ELEMENT, VECTOR_INT32_ELEMENT
)

from image_processing import image_processing

try:
    from .ImageProcessorBase import ImageProcessorBase
except ImportError:
    from imageProcessor.ImageProcessorBase import ImageProcessorBase


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


@KARABO_CLASSINFO("ImageProcessor", "2.4")
class ImageProcessor(ImageProcessorBase):
    # Numerical factor to convert gaussian standard deviation to beam size
    std_dev_2_beam_size = 4.0
    gauss_2_fwhm = 2 * math.sqrt(2 * math.log(2))
    averaging_time_interval = 1.0

    @staticmethod
    def expectedParameters(expected):
        output_data = Schema()
        (
            SLOT_ELEMENT(expected).key("reset")
            .displayedName("Reset Output")
            .description("Resets the processor output values.")
            .commit(),

            SLOT_ELEMENT(expected).key("useAsBackgroundImage")
            .displayedName("Current Image as Background")
            .description("Use the current image as background image.")
            .commit(),

            STRING_ELEMENT(expected).key("imagePath")
            .displayedName("Image Path")
            .description("Input image path.")
            .assignmentOptional().defaultValue("data.image")
            .expertAccess()
            .init()
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
            .description("The height of the incoming image. "
                         "Set to 1 for 1D images (spectra).")
            .unit(Unit.PIXEL)
            .readOnly()
            .commit(),

            INT32_ELEMENT(expected).key("imageOffsetY")
            .displayedName("Image Offset Y")
            .description("If the incoming image has a ROI, this "
                         "represents the Y position of the top-left "
                         "corner. "
                         "Set to 0 for 1D images (spectra).")
            .unit(Unit.PIXEL)
            .readOnly()
            .commit(),

            INT32_ELEMENT(expected).key("imageBinningY")
            .displayedName("Image Binning Y")
            .description("The image binning in the Y direction. "
                         "Set to 1 for 1D images (spectra).")
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

            NODE_ELEMENT(output_data).key("data")
            .displayedName("Data")
            .setDaqDataType(DaqDataType.TRAIN)
            .commit(),

            VECTOR_INT32_ELEMENT(output_data).key("data.imgBinCount")
            .displayedName("Pixel counts distribution")
            .description("Distribution of the image pixel counts.")
            .unit(Unit.NUMBER)
            .readOnly().initialValue([0])
            .commit(),

            VECTOR_DOUBLE_ELEMENT(output_data).key("data.imgX")
            .displayedName("X Distribution")
            .description("Image integral along the Y-axis.")
            .readOnly().initialValue([0])
            .commit(),

            VECTOR_DOUBLE_ELEMENT(output_data).key("data.imgY")
            .displayedName("Y Distribution")
            .description("Image integral along the X-axis.")
            .readOnly().initialValue([0])
            .commit(),

            OUTPUT_CHANNEL(expected).key("output")
            .displayedName("Output")
            .dataSchema(output_data)
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
        self.x_min = None
        self.x_max = None
        self.y_min = None
        self.y_max = None

        # Current image
        self.current_image = None

        # Background image
        self.bkg_image = None

        # Register additional slots
        self.KARABO_SLOT(self.reset)
        self.KARABO_SLOT(self.useAsBackgroundImage)
        # TODO: save/load bkg image slots

        # Processing time averages
        self.last_update_time = time.time()
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

    def initialization(self):
        """ This method will be called after the constructor. """
        self.reset()

    def useAsBackgroundImage(self):
        self.log.INFO("Use current image as background.")
        # Copy current image to background image
        self.bkg_image = np.array(self.current_image)

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

        h.set("inFrameRate", 0.)

        # Reset device parameters (all at once)
        self.set(h)

    def onData(self, data, metaData):
        first_image = False
        if self.get("state") == State.ON:
            self.log.INFO("Start of Stream")
            self.updateState(State.PROCESSING)
            first_image = True

        try:
            image_path = self['imagePath']
            if data.has(image_path):
                image_data = data[image_path]
            else:
                self.log.DEBUG(f"data does not have any image in {image_path}")
                return

            if isinstance(image_data, list):
                # Convert to ImageData
                data = np.asarray(image_data)
                dims = Dims(len(image_data))
                image_data = image_data(data, dims)

            if first_image:
                # Update warning levels
                dims = image_data.getDimensions()
                if len(dims) == 2:  # 2d
                    image_height = dims[0]
                    image_width = dims[1]
                elif len(dims) == 1:  # 1d
                    image_height = 1
                    image_width = dims[0]

                self.update_warn_levels(0, image_height, 0, image_width)

                bpp = image_data.getBitsPerPixel()
                self.update_output_schema(image_height, image_width, bpp)

            ts = Timestamp.fromHashAttributes(
                metaData.getAttributes('timestamp'))
            self.process_image(image_data, ts)  # Process image

        except Exception as e:
            msg = f"Exception caught in onData: {e}"
            self.update_alarm(error=True, msg=msg)

    def onEndOfStream(self, inputChannel):
        self.log.INFO("End of Stream")
        self['inFrameRate'] = 0.
        # Signals end of stream
        self.signalEndOfStream("output")
        self.updateState(State.ON)
        self['status'] = 'ON'

    def process_image(self, imageData, ts):
        filter_images_by_threshold = self.get("filterImagesByThreshold")
        image_threshold = self.get("imageThreshold")
        com_range = self.get("comRange")
        fit_range = self.get("fitRange")
        sigmas = self.get("rangeForAuto")
        abs_thr = self.get("absThreshold")
        thr = self.get("threshold")
        user_defined_range = self.get("userDefinedRange")
        absolute_positions = self.get("absolutePositions")

        h = Hash()  # Device properties updates
        out_hash = Hash()  # Output channel updates

        self.refresh_frame_rate_in()

        try:
            pixel_size = self.get("pixelSize")
        except Exception:
            # No pixel size
            pixel_size = None

        try:
            dims = imageData.getDimensions()
            if len(dims) == 2:
                image_height = dims[0]
                image_width = dims[1]
                is_2d_image = True
            elif len(dims) == 1:
                image_height = 1
                image_width = dims[0]
                is_2d_image = False
            else:
                self.log.DEBUG("Neither image nor spectrum. dims="
                               "{}".format(dims))

            if image_width != self.get("imageWidth"):
                h.set("imageWidth", image_width)
            if image_height != self.get("imageHeight"):
                h.set("imageHeight", image_height)

            roi_offsets = imageData.getROIOffsets()
            if is_2d_image:
                image_offset_y = roi_offsets[0]
                image_offset_x = roi_offsets[1]
            else:
                image_offset_y = 0
                image_offset_x = roi_offsets[0]
            if image_offset_x != self.get("imageOffsetX"):
                h.set("imageOffsetX", image_offset_x)
            if image_offset_y != self.get("imageOffsetY"):
                h.set("imageOffsetY", image_offset_y)

            image_binning = imageData.getBinning()
            if is_2d_image:
                image_binning_y = image_binning[0]
                image_binning_x = image_binning[1]
            else:
                image_binning_y = 1
                image_binning_x = image_binning[0]

            if image_binning_x != self.get("imageBinningX"):
                h.set("imageBinningX", image_binning_x)
            if image_binning_y != self.get("imageBinningY"):
                h.set("imageBinningY", image_binning_y)

            self.current_image = imageData.getData()  # np.ndarray
            img = self.current_image  # Shallow copy
            if img.ndim == 3 and img.shape[2] == 1:
                # Image has 3rd dimension (channel), but it's 1
                self.log.DEBUG("Reshaping image...")
                img = img.squeeze()

            self.log.DEBUG("Image loaded!!!")

        except Exception as e:
            msg = f"Exception when opening image: {e}"
            self.update_alarm(error=True, msg=msg)
            return

        # Filter by Threshold
        if filter_images_by_threshold:
            if img.max() < image_threshold:
                self.log.DEBUG("Max pixel value below threshold: image "
                               "discarded!!!")
                return

        # Get pixel min/max/mean values
        if self.get("doMinMaxMean"):
            t0 = time.time()
            try:
                img_min = img.min()
                img_max = img.max()
                img_mean = img.mean()
            except Exception as e:
                msg = f"Exception caught whilst calculating min/max/mean: {e}"
                self.update_alarm(error=True, msg=msg)
                return

            t1 = time.time()
            self.averagers["minMaxMeanTime"].append(t1 - t0)

            h.set("minPxValue", float(img_min))
            h.set("maxPxValue", float(img_max))
            h.set("meanPxValue", float(img_mean))
            self.log.DEBUG("Pixel min/max/mean: done!")
        else:
            h.set("minPxValue", 0.0)
            h.set("maxPxValue", 0.0)
            h.set("meanPxValue", 0.0)

        # Frequency of Pixel Values
        if self.get("doBinCount"):
            t0 = time.time()
            try:
                px_freq = image_processing.imagePixelValueFrequencies(img)

                self.log.DEBUG("Pixel values distribution: done!")
            except Exception as e:
                msg = f"Exception caught whilst counting value frequency: {e}"
                self.update_alarm(error=True, msg=msg)
                return

            t1 = time.time()
            self.averagers["binCountTime"].append(t1 - t0)

            out_hash.set("data.imgBinCount", px_freq.tolist())
        else:
            out_hash.set("data.imgBinCount", [0])

        # Background image subtraction
        if self.get("subtractBkgImage"):
            t0 = time.time()
            try:
                if(self.bkg_image is not None and
                   self.bkg_image.shape == img.shape):

                    if self.current_image is img:
                        # Must copy, or self.currentImage will be modified
                        self.current_image = img.copy()

                    # Subtract background image
                    m = (img > self.bkg_image)  # img is above bkg
                    n = (img <= self.bkg_image)  # image is below bkg

                    # subtract bkg from img, where img is above bkg
                    img[m] -= self.bkg_image[m]
                    img[n] = 0  # zero img, where its is below bkg

            except Exception as e:
                msg = f"Exception caught during background subtraction: {e}"
                self.update_alarm(error=True, msg=msg)
                return

            t1 = time.time()
            self.averagers["subtractBkgImageTime"].append(t1 - t0)
            self.log.DEBUG("Background image subtraction: done!")

        # Pedestal subtraction
        if self.get("subtractImagePedestal"):  # was "doBackground"
            t0 = time.time()
            try:
                img_min = img.min()
                if img_min > 0:
                    if self.current_image is img:
                        # Must copy, or self.currentImage will be modified
                        self.current_image = img.copy()

                    # Subtract image pedestal
                    img -= img_min

            except Exception as e:
                msg = f"Exception caught during pedestal subtraction: {e}"
                self.update_alarm(error=True, msg=msg)
                return

            t1 = time.time()
            self.averagers["subtractPedestalTime"].append(t1 - t0)
            self.log.DEBUG("Image pedestal subtraction: done!")

        # Sum the image along the x- and y-axes
        img_x = None
        img_y = None
        if self.get("doXYSum") and is_2d_image:
            t0 = time.time()
            try:
                x_min = np.maximum(user_defined_range[0], 0)
                x_max = np.minimum(user_defined_range[1], image_width)
                y_min = np.maximum(user_defined_range[2], 0)
                y_max = np.minimum(user_defined_range[3], image_height)
                data = img[y_min:y_max, x_min:x_max]
                # Sums along Y- and X-axes
                img_x = image_processing.imageSumAlongY(data)
                img_y = image_processing.imageSumAlongX(data)

            except Exception as e:
                msg = f"Exception caught during x/y integration: {e}"
                self.update_alarm(error=True, msg=msg)
                return

            if img_x is None or img_y is None:
                self.log.WARN("Could not sum image along x or y axis.")
                return

            t1 = time.time()
            self.averagers["xYSumTime"].append(t1 - t0)

            out_hash.set("data.imgX", img_x.astype(np.float).tolist())
            out_hash.set("data.imgY", img_y.astype(np.float).tolist())
            self.log.DEBUG("Image X-Y sums: done!")
        else:
            out_hash.set("data.imgX", [0.0])
            out_hash.set("data.imgY", [0.0])

        # Centre-of-Mass and widths
        x0 = None
        y0 = None
        sx = None
        sy = None
        if self.get("doCOfM") or self.get("do1DFit") or self.get("do2DFit"):
            t0 = time.time()
            try:
                # Set a threshold to cut away noise
                if abs_thr > 0.0:
                    img2 = image_processing.\
                        imageSetThreshold(img, min(abs_thr, img.max()),
                                          copy=True)

                else:
                    img2 = image_processing.\
                        imageSetThreshold(img, thr * img.max(), copy=True)

                # Centre-of-Mass and widths
                if is_2d_image:
                    if com_range == "user-defined":
                        img3 = img2[user_defined_range[2]:
                                    user_defined_range[3],
                                    user_defined_range[0]:
                                    user_defined_range[1]]
                        x0, y0, sx, sy = image_processing.\
                            imageCentreOfMass(img3)
                        x0 += user_defined_range[0]
                        y0 += user_defined_range[2]
                    else:  # "full"
                        x0, y0, sx, sy = image_processing.\
                            imageCentreOfMass(img2)
                else:  # 1d
                    if com_range == "user-defined":

                        img3 = img2[user_defined_range[0]:
                                    user_defined_range[1]]
                        (x0, sx) = image_processing.imageCentreOfMass(img3)
                        x0 += user_defined_range[0]
                    else:  # "full"
                        (x0, sx) = image_processing.imageCentreOfMass(img2)
                    y0 = 0
                    sy = 0

                if fit_range == "full":
                    x_min = 0
                    x_max = image_width
                    y_min = 0
                    y_max = image_height
                elif fit_range == "user-defined":
                    x_min = np.maximum(user_defined_range[0], 0)
                    x_max = np.minimum(user_defined_range[1], image_width)
                    y_min = np.maximum(user_defined_range[2], 0)
                    y_max = np.minimum(user_defined_range[3], image_height)
                    # TODO check that x_min<x_max and y_min<y_max
                else:  # "auto"
                    x_min, x_max, y_min, y_max = self.auto_fit_range(
                        x0, y0, sx, sy, sigmas, image_width, image_height)


            except Exception as e:
                msg = f"Exception caught whilst calculating CoM: {e}"
                self.update_alarm(error=True, msg=msg)
                return

            t1 = time.time()
            self.averagers["cOfMTime"].append(t1 - t0)

            if absolute_positions:
                h.set("x0", image_binning_x*(x0 + image_offset_x))
                h.set("y0", image_binning_y*(y0 + image_offset_y))
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
            gauss1d_start_values = self.get("gauss1dStartValues")

            t0 = time.time()
            try:
                if img_x is None:
                    if is_2d_image:
                        img_x = image_processing.imageSumAlongY(img)
                    else:
                        img_x = img

                # Select sub-range and substract pedestal
                data = img_x[x_min:x_max]
                img_min = data.min()
                if img_min > 0:
                    data -= data.min()

                # Initial parameters
                if gauss1d_start_values == "raw_peak":
                    # evaluate peak parameters w/o fit
                    p0 = self.eval_starting_point(data)
                elif gauss1d_start_values == "last_fit_result":
                    if None not in (self.ax1d, self.x01d, self.sx1d):
                        # Use last fit's parameters as initial estimate
                        p0 = (self.ax1d, self.x01d - x_min, self.sx1d)
                    elif None not in (x0, sx):
                        # Use CoM for initial parameter estimate
                        p0 = (data.max(), x0 - x_min, sx)
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
                p_x = out[0]  # parameters
                c_x = out[1]  # covariance
                success_x = out[2]  # error

                # Save fit's parameters
                self.ax1d, self.x01d, self.sx1d = (p_x[0], p_x[1] + x_min,
                                                   p_x[2])

            except Exception as e:
                msg = f"Exception caught during gaussian fit [x]: {e}"
                self.update_alarm(error=True, msg=msg)
                return

            t1 = time.time()

            if is_2d_image:
                try:
                    if img_y is None:
                        img_y = image_processing.imageSumAlongX(img)

                    # Select sub-range and substract pedestal
                    data = img_y[y_min:y_max]
                    imgMin = data.min()
                    if imgMin > 0:
                        data -= data.min()

                    # Initial parameters
                    if gauss1d_start_values == "raw_peak":
                        # evaluate peak parameters w/o fit
                        p0 = self.evalStartingPoint(data)
                    elif gauss1d_start_values == "last_fit_result":
                        if None not in (self.ay1d, self.y01d, self.sy1d):
                            # Use last fit's parameters as initial estimate
                            p0 = (self.ay1d, self.y01d - y_min, self.sy1d)
                        elif None not in (y0, sy):
                            # Use CoM for initial parameter estimate
                            p0 = (data.max(), y0 - y_min, sy)
                        else:
                            # No initial parameters
                            p0 = None
                            # TODO may use "p0 = self.evalStartingPoint(data)"
                            # as well, once it's well tested

                    else:
                        raise RuntimeError("unexpected gauss1dStartValues "
                                           "option")

                    # 1D gaussian fit
                    out = image_processing.fitGauss(
                        data, p0, enablePolynomial=enable_polynomial)
                    p_y = out[0]  # parameters
                    c_y = out[1]  # covariance
                    success_y = out[2]  # error

                    # Save fit's parameters
                    self.ay1d, self.y01d, self.sy1d = (p_y[0], p_y[1] + y_min,
                                                       p_y[2])

                except Exception as e:
                    msg = f"Exception caught during gaussian fit [y]: {e}"
                    self.update_alarm(error=True, msg=msg)
                    return

                t2 = time.time()

            self.averagers["xFitTime"].append(t1 - t0)
            h.set("xFitSuccess", success_x)

            if success_x in (1, 2, 3, 4):
                # Successful fit

                if c_x is None:
                    self.log.WARN("Successful X fit with singular covariance "
                                  "matrix. Resetting initial fit values.")
                    self.ax1d = None
                    self.x01d = None
                    self.sx1d = None

                try:
                    if absolute_positions:
                        h.set("x01d", image_binning_x
                              * (x_min + p_x[1] + image_offset_x))
                    else:
                        h.set("x01d", x_min + p_x[1])

                    if c_x is not None:
                        ex01d = math.sqrt(c_x[1][1])
                        esx1d = math.sqrt(c_x[2][2])
                    else:
                        ex01d = 0.0
                        esx1d = 0.0

                    h.set("ex01d", ex01d)
                    h.set("esx1d", esx1d)
                    h.set("sx1d", p_x[2])

                    if pixel_size is not None:
                        beam_width = (self.std_dev_2_beam_size * pixel_size
                                      * p_x[2])
                        h.set("beamWidth1d", beam_width)

                except Exception as e:
                    msg = f"Exception caught during gaussian fit [x]: {e}"
                    self.update_alarm(error=True, msg=msg)
                    return

            if is_2d_image:
                self.averagers["yFitTime"].append(t2 - t1)
                h.set("yFitSuccess", success_y)

                if success_y in (1, 2, 3, 4):
                    # Successful fit

                    if c_y is None:
                        self.log.WARN("Successful Y fit with singular "
                                      "covariance matrix."
                                      " Resetting initial fit values.")
                        self.ay1d = None
                        self.y01d = None
                        self.sy1d = None

                    try:
                        if absolute_positions:
                            h.set("y01d", image_binning_y
                                  * (y_min + p_y[1] + image_offset_y))
                        else:
                            h.set("y01d", y_min + p_y[1])

                        if c_y is not None:
                            ey01d = math.sqrt(c_y[1][1])
                            esy1d = math.sqrt(c_y[2][2])
                        else:
                            ey01d = 0.0
                            esy1d = 0.0
                        h.set("ey01d", ey01d)
                        h.set("esy1d", esy1d)

                        h.set("sy1d", p_y[2])

                        if pixel_size is not None:
                            beam_height = (self.std_dev_2_beam_size
                                           * pixel_size * p_y[2])
                            h.set("beamHeight1d", beam_height)

                    except Exception as e:
                        msg = f"Exception caught during gaussian fit [y]: {e}"
                        self.update_alarm(error=True, msg=msg)
                        return

                if success_x in (1, 2, 3, 4) and success_y in (1, 2, 3, 4):
                    ax1d = p_x[0] / p_y[2] / math.sqrt(2 * math.pi)
                    ay1d = p_y[0] / p_x[2] / math.sqrt(2 * math.pi)
                    h.set("ax1d", ax1d)
                    h.set("ay1d", ay1d)

            else:  # 1d
                if success_x in (1, 2, 3, 4):
                    h.set("ax1d", p_x[0])

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
        if self.get("do2DFit") and is_2d_image:
            enable_polynomial = self.get("enablePolynomial")

            t0 = time.time()
            try:
                # Input data
                data = img[y_min:y_max, x_min:x_max]
                img_min = data.min()
                if img_min > 0:
                    data -= data.min()

                if rotation:

                    # Initial parameters
                    if None not in (self.a2d, self.x02d, self.y02d,
                                    self.sx2d, self.sy2d, self.theta2d):
                        # Use last fit's parameters as initial estimate
                        p0 = (self.a2d, self.x02d - x_min, self.y02d - y_min,
                              self.sx2d, self.sy2d, self.theta2d)
                    elif None not in (x0, y0, sx, sy):
                        # Use CoM for initial parameter estimate
                        p0 = (data.max(), x0 - x_min, y0 - y_min, sx, sy, 0.0)
                    else:
                        p0 = None

                    # 2D gaussian fit
                    out = image_processing.fitGauss2DRot(
                        data, p0, enablePolynomial=enable_polynomial)
                    p_xy = out[0]  # parameters: A, x0, y0, sx, sy, theta
                    c_xy = out[1]  # covariance
                    success_xy = out[2]  # error

                    # Save fit's parameters
                    self.a2d, self.x02d, self.y02d, self.sx2d, self.sy2d = (
                        p_xy[0], p_xy[1] + x_min, p_xy[2] + y_min, p_xy[3],
                        p_xy[4])
                    self.theta2d = p_xy[5]

                else:

                    # Initial parameters
                    if None not in (self.a2d, self.x02d, self.y02d,
                                    self.sx2d, self.sy2d):
                        # Use last fit's parameters as initial estimate
                        p0 = (self.a2d, self.x02d - x_min, self.y02d - y_min,
                              self.sx2d, self.sy2d)
                    elif None not in (x0, y0, sx, sy):
                        # Use CoM for initial parameter estimate
                        p0 = (data.max(), x0 - x_min, y0 - y_min, sx, sy)
                    else:
                        p0 = None

                    # 2D gaussian fit
                    out = image_processing.fitGauss(
                        data, p0, enablePolynomial=enable_polynomial)
                    p_xy = out[0]  # parameters: A, x0, y0, sx, sy
                    c_xy = out[1]  # covariance
                    success_xy = out[2]  # error

                    # Save fit's parameters
                    self.a2d, self.x02d, self.y02d, self.sx2d, self.sy2d = (
                        p_xy[0], p_xy[1] + x_min, p_xy[2] + y_min, p_xy[3],
                        p_xy[4])

            except Exception as e:
                msg = f"Exception caught during 2D gaussian fit: {e}"
                self.update_alarm(error=True, msg=msg)
                return

            t1 = time.time()

            self.averagers["fitTime"].append(t1 - t0)
            h.set("fitSuccess", success_xy)

            if success_xy in (1, 2, 3, 4):
                # Successful fit
                h.set("a2d", p_xy[0])

                if c_xy is None:
                    self.log.WARN("Successful XY fit with singular covariance "
                                  "matrix. Resetting initial fit values.")
                    self.a2d = None
                    self.x02d = None
                    self.y02d = None
                    self.sx2d = None
                    self.sy2d = None
                    if rotation:
                        self.theta2d = None

                if absolute_positions:
                    h.set("x02d",
                          image_binning_x*(x_min + p_xy[1] + image_offset_x))
                    h.set("y02d",
                          image_binning_y*(y_min + p_xy[2] + image_offset_y))
                else:
                    h.set("x02d", x_min + p_xy[1])
                    h.set("y02d", y_min + p_xy[2])

                if c_xy is not None:
                    h.set("ex02d", math.sqrt(c_xy[1][1]))
                    h.set("ey02d", math.sqrt(c_xy[2][2]))
                    h.set("esx2d", math.sqrt(c_xy[3][3]))
                    h.set("esy2d", math.sqrt(c_xy[4][4]))
                else:
                    h.set("ex02d", 0.0)
                    h.set("ey02d", 0.0)
                    h.set("esx2d", 0.0)
                    h.set("esy2d", 0.0)

                h.set("sx2d", p_xy[3])
                h.set("sy2d", p_xy[4])

                if pixel_size is not None:
                    beam_width = (self.std_dev_2_beam_size * pixel_size
                                  * p_xy[3])
                    h.set("beamWidth2d", beam_width)
                    beam_height = (self.std_dev_2_beam_size * pixel_size
                                   * p_xy[4])
                    h.set("beamHeight2d", beam_height)
                if rotation:
                    h.set("theta2d", p_xy[5] % (2. * math.pi))
                    if c_xy is not None:
                        h.set("etheta2d", math.sqrt(c_xy[5][5]))
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
        integration_done = False
        if self['doIntegration']:
            try:
                t0 = time.time()
                integrationRegion = self.get("integrationRegion")
                x_min = np.maximum(integrationRegion[0], 0)
                x_max = np.minimum(integrationRegion[1], image_width)
                y_min = np.maximum(integrationRegion[2], 0)
                y_max = np.minimum(integrationRegion[3], image_height)
                if is_2d_image:
                    data = img[y_min:y_max, x_min:x_max]
                else:
                    data = img[x_min:x_max]

                integral = np.float64(np.sum(data))
                h.set("regionIntegral", integral)
                region_mean = integral / data.size if data.size > 0 else 0.0
                h.set("regionMean", region_mean)
                t1 = time.time()
                self.averagers["integrationTime"].append(t1 - t0)
                integration_done = True
                self.log.DEBUG("Region integration: done!")
            except Exception as e:
                msg = f"Exception caught during region integration: {e}"
                self.update_alarm(error=True, msg=msg)
                return

        if not integration_done:
            h.set("regionIntegral", 0.0)
            h.set("regionMean", 0.0)

        if time.time() - self.last_update_time > self.averaging_time_interval:
            # average processing times over 1 second
            for key, averager in self.averagers.items():
                if averager:
                    h.set(key, averager.mean())
                    averager.clear()

            self.last_update_time = time.time()

        # Update device parameters (all at once)
        self.set(h, ts)
        self.writeChannel("output", out_hash, ts)
        self.update_alarm()  # Success

    def eval_starting_point(self, data):
        fit_ampl, peak_pixel, fwhm = image_processing.peakParametersEval(data)

        return fit_ampl, peak_pixel, fwhm/self.gauss_2_fwhm

    def update_warn_levels(self, x_min, x_max, y_min, y_max):
        new_schema = Schema()
        needs_update = False

        if x_min != self.x_min or x_max != self.x_max:
            (
                DOUBLE_ELEMENT(new_schema).key("x01d")
                .displayedName("x0 (1D Fit)")
                .description("x0 from 1D Fit.")
                .unit(Unit.PIXEL)
                .readOnly()
                .warnLow(x_min).needsAcknowledging(False)
                .warnHigh(x_max).needsAcknowledging(False)
                .commit(),

                DOUBLE_ELEMENT(new_schema).key("x02d")
                .displayedName("x0 (2D Fit)")
                .description("x0 from 2D Fit.")
                .unit(Unit.PIXEL)
                .readOnly()
                .warnLow(x_min).needsAcknowledging(False)
                .warnHigh(x_max).needsAcknowledging(False)
                .commit(),
            )
            self.x_min = x_min
            self.x_max = x_max
            needs_update = True

        if y_min != self.y_min or y_max != self.y_max:
            (
                DOUBLE_ELEMENT(new_schema).key("y01d")
                .displayedName("y0 (1D Fit)")
                .description("y0 from 1D Fit.")
                .unit(Unit.PIXEL)
                .readOnly()
                .warnLow(y_min).needsAcknowledging(False)
                .warnHigh(y_max).needsAcknowledging(False)
                .commit(),

                DOUBLE_ELEMENT(new_schema).key("y02d")
                .displayedName("y0 (2D Fit)")
                .description("y0 from 2D Fit.")
                .unit(Unit.PIXEL)
                .readOnly()
                .warnLow(y_min).needsAcknowledging(False)
                .warnHigh(y_max).needsAcknowledging(False)
                .commit(),
            )
            self.y_min = y_min
            self.y_max = y_max
            needs_update = True

        if needs_update:
            self.updateSchema(new_schema)

    def update_output_schema(self, width, height, bpp):
        # Get device configuration before schema update
        try:
            output_hostname = self["output.hostname"]
        except AttributeError as e:
            # Configuration does not contain "output.hostname"
            output_hostname = None

        new_schema = Schema()
        output_data = Schema()
        (
            NODE_ELEMENT(output_data).key("data")
            .displayedName("Data")
            .setDaqDataType(DaqDataType.TRAIN)
            .commit(),

            VECTOR_INT32_ELEMENT(output_data).key("data.imgBinCount")
            .displayedName("Pixel counts distribution")
            .description("Distribution of the image pixel counts.")
            .unit(Unit.NUMBER)
            .maxSize(min(65535, 2**bpp))
            .readOnly().initialValue([0])
            .commit(),

            VECTOR_DOUBLE_ELEMENT(output_data).key("data.imgX")
            .displayedName("X Distribution")
            .description("Image sum along the Y-axis.")
            .maxSize(width)
            .readOnly().initialValue([0])
            .commit(),

            VECTOR_DOUBLE_ELEMENT(output_data).key("data.imgY")
            .displayedName("Y Distribution")
            .description("Image sum along the X-axis.")
            .maxSize(height)
            .readOnly().initialValue([0])
            .commit(),

            OUTPUT_CHANNEL(new_schema).key("output")
            .displayedName("Output")
            .dataSchema(output_data)
            .commit(),
        )

        self.updateSchema(new_schema)

        if output_hostname:
            # Restore configuration
            self.log.DEBUG(f"output.hostname: {output_hostname}")
            self.set("output.hostname", output_hostname)

    @staticmethod
    def auto_fit_range(x0, y0, sx, sy, sigmas, image_width, image_height,
                       min_range=10):

        def increase_range(low_val, high_val, maximum_val, target_range):
            missing = target_range - (high_val - low_val)
            if missing > 0:
                low_val = np.maximum(0, low_val - missing // 2)
                missing = target_range - (high_val - low_val)
                high_val = np.minimum(maximum_val, high_val + missing)
                missing = target_range - (high_val - low_val)
                if missing > 0:
                    low_val = np.maximum(0, low_val - missing)
            return low_val, high_val

        x_min = np.maximum(int(x0 - sigmas * sx), 0)
        x_max = np.minimum(int(x0 + sigmas * sx), image_width)
        y_min = np.maximum(int(y0 - sigmas * sy), 0)
        y_max = np.minimum(int(y0 + sigmas * sy), image_height)

        # ensure that auto range contains at least min_range pixels
        x_min, x_max = increase_range(x_min, x_max, image_width, min_range)
        y_min, y_max = increase_range(y_min, y_max, image_height, min_range)

        return x_min, x_max, y_min, y_max


