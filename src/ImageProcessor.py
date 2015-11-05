#!/usr/bin/env python

# TODO: display 1d and 2d fits

__author__="andrea.parenti@xfel.eu"
__date__ ="October 10, 2013, 10:29 AM"
__copyright__="Copyright (c) 2010-2013 European XFEL GmbH Hamburg. All rights reserved."

import math
import numpy
import time

from karabo.device import *
from karabo.ok_error_fsm import OkErrorFsm

from image_processing import image_processing

@KARABO_CLASSINFO("ImageProcessor", "1.3")
class ImageProcessor(PythonDevice, OkErrorFsm):

    # Numerical factor to convert gaussian standard deviation to beam size
    stdDev2BeamSize = 4.0

    def __init__(self, configuration):
        # always call superclass constructor first!
        super(ImageProcessor,self).__init__(configuration)

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

        # Register additional slots
        self._ss.registerSlot(self.useAsBackgroundImage)
        # TODO: save/load bkg image slots

    def __del__(self):
        super(ImageProcessor, self).__del__()

    @staticmethod
    def expectedParameters(expected):
        data = Schema()

        e = SLOT_ELEMENT(expected).key("useAsBackgroundImage")
        e.displayedName("Current Image as Background")
        e.description("Use the current image as background image.")
        e.commit()

        (
        IMAGEDATA(data).key("image")
        .commit(),

        INPUT_CHANNEL(expected).key("input")
                .displayedName("Input")
                .dataSchema(data)
                .commit(),

        # Images should be dropped if processor is too slow
        OVERWRITE_ELEMENT(expected).key("input.onSlowness")
                .setNewDefaultValue("drop")
                .commit(),
        )

        e = INT32_ELEMENT(expected).key("imageWidth")
        e.displayedName("Image Width")
        e.description("The image width.")
        e.unit(PIXEL)
        e.readOnly()
        e.commit()
        
        e = INT32_ELEMENT(expected).key("imageOffsetX")
        e.displayedName("Image Offset X")
        e.description("The image offset in X direction, i.e. the Y position of its top-left corner.")
        e.unit(PIXEL)
        e.readOnly()
        e.commit()
        
        e = INT32_ELEMENT(expected).key("imageHeight")
        e.displayedName("Image Height")
        e.description("The image height.")
        e.unit(PIXEL)
        e.readOnly()
        e.commit()
        
        e = INT32_ELEMENT(expected).key("imageOffsetY")
        e.displayedName("Image Offset Y")
        e.description("The image offset in Y direction, i.e. the Y position of its top-left corner.")
        e.unit(PIXEL)
        e.readOnly()
        e.commit()
        
        e = FLOAT_ELEMENT(expected).key("pixelSize")
        e.displayedName("Pixel Size")
        e.description("The pixel size.")
        e.assignmentOptional().noDefaultValue()
        e.unit(Unit.METER).metricPrefix(MetricPrefix.MICRO)
        e.reconfigurable()
        e.commit()
        
        e = BOOL_ELEMENT(expected).key("filterImagesByThreshold")
        e.displayedName("Filter Images by Threshold")
        e.description("If True, images will be fitted only if maximum pixel value exceeds user's defined threshold.")
        e.assignmentOptional().defaultValue(False)
        e.reconfigurable()
        e.commit()
        
        e = FLOAT_ELEMENT(expected).key("imageThreshold")
        e.displayedName("Image Threshold")
        e.description("The threshold for image fitting.")
        e.assignmentOptional().defaultValue(0.)
        e.unit(NUMBER)
        e.reconfigurable()
        e.commit()
        
        e = STRING_ELEMENT(expected).key("fitRange")
        e.displayedName("Fit Range")
        e.description("The range to be used for fitting. Can be the full image, auto-determined range, user-defined range.")
        e.assignmentOptional().defaultValue("auto")
        e.options("full auto user-defined")
        e.reconfigurable()
        e.commit()
        
        e = FLOAT_ELEMENT(expected).key("rangeForAuto")
        e.displayedName("Range for Auto")
        e.description("The range for auto mode (in standard deviations).")
        e.assignmentOptional().defaultValue(3.0)
        e.reconfigurable()
        e.commit()
        
        e = VECTOR_INT32_ELEMENT(expected).key("userDefinedRange")
        e.displayedName("User Defined Range")
        e.description("The user-defined range for centre-of-gravity and gaussian fit(s).")
        e.assignmentOptional().defaultValue([0, 400, 0, 400])
        e.reconfigurable()
        e.commit()
        
        e = BOOL_ELEMENT(expected).key("absolutePositions")
        e.displayedName("Peak Absolute Position")
        e.description("If True, the peak position will be w.r.t. to the full frame, not to the ROI.")
        e.assignmentOptional().defaultValue(True)
        e.reconfigurable()
        e.commit()
        
        e = FLOAT_ELEMENT(expected).key("threshold")
        e.displayedName("Pixel Relative threshold")
        e.description("The pixel threshold for centre-of-gravity calculation (fraction of highest value).")
        e.assignmentOptional().defaultValue(0.10)
        e.minInc(0.0).maxInc(1.0)
        e.reconfigurable()
        e.commit()
                
        # Image processing enable bits
        
        e = BOOL_ELEMENT(expected).key("doMinMaxMean")
        e.displayedName("Min/Max/Mean")
        e.description("Get the following information from the pixels: min, max, mean value.")
        e.assignmentOptional().defaultValue(True)
        e.reconfigurable()
        e.commit()
        
        e = BOOL_ELEMENT(expected).key("doBinCount")
        e.displayedName("Pixel Value Frequency")
        e.description("Frequency distribution of pixel values.")
        e.assignmentOptional().defaultValue(True)
        e.reconfigurable()
        e.commit()

        e = BOOL_ELEMENT(expected).key("subtractBkgImage")
        e.displayedName("Subtract Background Image")
        e.description("Subtract the background image.")
        e.assignmentOptional().defaultValue(False)
        e.reconfigurable()
        e.commit()

        e = BOOL_ELEMENT(expected).key("subtractImagePedestal")  # was "doBackground"
        e.displayedName("Subtract Image Pedestal")
        e.description("Subtract the image pedestal (ie image = image - image.min()).")
        e.assignmentOptional().defaultValue(True)
        e.reconfigurable()
        e.commit()

        e = BOOL_ELEMENT(expected).key("doXYSum")  # was "doProjection"
        e.displayedName("Sum along X-Y Axes")
        e.description("Sum image along the x- and y-axes.")
        e.assignmentOptional().defaultValue(True)
        e.reconfigurable()
        e.commit()
        
        e = BOOL_ELEMENT(expected).key("doCOfM")
        e.displayedName("Centre-Of-Mass")
        e.description("Calculates centre-of-mass and widths.")
        e.assignmentOptional().defaultValue(True)
        e.reconfigurable()
        e.commit()
        
        e = BOOL_ELEMENT(expected).key("do1DFit")
        e.displayedName("1-D Gaussian Fits")
        e.description("Perform a 1-d gaussian fit of the x- and y-distributions.")
        e.assignmentOptional().defaultValue(True)
        e.reconfigurable()
        e.commit()
        
        e = BOOL_ELEMENT(expected).key("do2DFit")
        e.displayedName("2-D Gaussian Fit")
        e.description("Perform a 2-d gaussian fits.")
        e.assignmentOptional().defaultValue(False)
        e.reconfigurable()
        e.commit()
        
        e = BOOL_ELEMENT(expected).key("doGaussRotation")
        e.displayedName("Allow Gaussian Rotation")
        e.description("Allow the 2D gaussian to be rotated.")
        e.assignmentOptional().defaultValue(False)
        e.reconfigurable()
        e.commit()
        
        # Image processing times
        
        e = FLOAT_ELEMENT(expected).key("minMaxMeanTime")
        e.displayedName("Min/Max/Mean Evaluation Time")
        e.unit(SECOND)
        e.readOnly()
        e.commit()
        
        e = FLOAT_ELEMENT(expected).key("binCountTime")
        e.displayedName("Pixel Value Frequency Time")
        e.unit(SECOND)
        e.readOnly()
        e.commit()

        e = FLOAT_ELEMENT(expected).key("subtractBkgImageTime")
        e.displayedName("Background Image Subtraction Time")
        e.unit(SECOND)
        e.readOnly()
        e.commit()

        e = FLOAT_ELEMENT(expected).key("subtractPedestalTime")  # was "backgroundTime"
        e.displayedName("Pedestal Subtraction Time")
        e.unit(SECOND)
        e.readOnly()
        e.commit()

        e = FLOAT_ELEMENT(expected).key("xYSumTime")
        e.displayedName("Image X-Y Sums Time")
        e.unit(SECOND)
        e.readOnly()
        e.commit()
        
        e = FLOAT_ELEMENT(expected).key("cOfMTime")
        e.displayedName("Centre-Of-Mass Time")
        e.unit(SECOND)
        e.readOnly()
        e.commit()
        
        e = FLOAT_ELEMENT(expected).key("xFitTime")
        e.displayedName("1D Gaussian Fit Time (X distribution)")
        e.unit(SECOND)
        e.readOnly()
        e.commit()
        
        e = FLOAT_ELEMENT(expected).key("yFitTime")
        e.displayedName("1D Gaussian Fit Time (Y distribution)")
        e.unit(SECOND)
        e.readOnly()
        e.commit()
        
        e = FLOAT_ELEMENT(expected).key("fitTime")
        e.displayedName("2D Gaussian Fit Time")
        e.unit(SECOND)
        e.readOnly()
        e.commit()
        
        # Image processing outputs
        
        e = DOUBLE_ELEMENT(expected).key("minPxValue")
        e.displayedName("Min Px Value")
        e.description("Minimun pixel value.")
        e.unit(NUMBER)
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("maxPxValue")
        e.displayedName("Max Pixel Value")
        e.description("Maximun pixel value.")
        e.unit(NUMBER)
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("meanPxValue")
        e.displayedName("Mean Pixel Value")
        e.description("Mean pixel value.")
        e.unit(NUMBER)
        e.readOnly()
        e.commit()
        
        e = VECTOR_DOUBLE_ELEMENT(expected).key("imgBinCount")
        e.displayedName("Pixel counts distribution")
        e.description("Distribution of the image pixel counts.")
        e.unit(NUMBER)
        e.readOnly().initialValue([0])
        e.commit()
        
        e = VECTOR_DOUBLE_ELEMENT(expected).key("imgX")
        e.displayedName("X Distribution")
        e.description("Image sum along the Y-axis.")
        e.readOnly().initialValue([0])
        e.commit()
        
        e = VECTOR_DOUBLE_ELEMENT(expected).key("imgY")
        e.displayedName("Y Distribution")
        e.description("Image sum along the X-axis.")
        e.readOnly().initialValue([0])
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("x0")
        e.displayedName("x0 (Centre-Of-Mass)")
        e.description("x0 from centre-of-mass.")
        e.unit(PIXEL)
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("sx")
        e.displayedName("sigma_x (Centre-Of-Mass)")
        e.description("sigma_x from centre-of-mass.")
        e.unit(PIXEL)
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("y0")
        e.displayedName("y0 (Centre-Of-Mass)")
        e.description("y0 from Centre-Of-Mass.")
        e.unit(PIXEL)
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("sy")
        e.displayedName("sigma_y (Centre-Of-Mass)")
        e.description("sigma_y from Centre-Of-Mass.")
        e.unit(PIXEL)
        e.readOnly()
        e.commit()
        
        e = INT32_ELEMENT(expected).key("xFitSuccess")
        e.displayedName("x Success (1D Fit)")
        e.description("1-D Gaussian Fit Success (1-4 if fit converged).")
        e.unit(PIXEL)
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("ax1d")
        e.displayedName("Ax (1D Fit)")
        e.description("Amplitude Ax from 1D Fit.")
        e.unit(NUMBER)
        e.readOnly()
        e.commit()

        e = DOUBLE_ELEMENT(expected).key("x01d")
        e.displayedName("x0 (1D Fit)")
        e.description("x0 from 1D Fit.")
        e.unit(PIXEL)
        e.readOnly()
        e.commit()

        e = DOUBLE_ELEMENT(expected).key("ex01d")
        e.displayedName("sigma(x0) (1D Fit)")
        e.description("Uncertainty on x0 from 1D Fit.")
        e.expertAccess()
        e.unit(PIXEL)
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("sx1d")
        e.displayedName("sigma_x (1D Fit)")
        e.description("sigma_x from 1D Fit.")
        e.unit(PIXEL)
        e.readOnly()
        e.commit()

        e = DOUBLE_ELEMENT(expected).key("esx1d")
        e.displayedName("sigma(sigma_x) (1D Fit)")
        e.description("Uncertainty on sigma_x from 1D Fit.")
        e.expertAccess()
        e.unit(PIXEL)
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("beamWidth1d")
        e.displayedName("Beam Width (1D Fit)")
        e.description("Beam width from 1D Fit. Defined as 4x sigma_x.")
        e.unit(Unit.METER).metricPrefix(MetricPrefix.MICRO)
        e.readOnly()
        e.commit()
        
        e = INT32_ELEMENT(expected).key("yFitSuccess")
        e.displayedName("y Success (1D Fit)")
        e.description("1-D Gaussian Fit Success (1-4 if fit converged).")
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("ay1d")
        e.displayedName("Ay (1D Fit)")
        e.description("Amplitude Ay from 1D Fit.")
        e.unit(NUMBER)
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("y01d")
        e.displayedName("y0 (1D Fit)")
        e.description("y0 from 1D Fit.")
        e.unit(PIXEL)
        e.readOnly()
        e.commit()

        e = DOUBLE_ELEMENT(expected).key("ey01d")
        e.displayedName("sigma(y0) (1D Fit)")
        e.description("Uncertainty on y0 from 1D Fit.")
        e.expertAccess()
        e.unit(PIXEL)
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("sy1d")
        e.displayedName("sigma_y (1D Fit)")
        e.description("sigma_y from 1D Fit.")
        e.unit(PIXEL)
        e.readOnly()
        e.commit()

        e = DOUBLE_ELEMENT(expected).key("esy1d")
        e.displayedName("sigma(sigma_y) (1D Fit)")
        e.description("Uncertainty on sigma_y from 1D Fit.")
        e.expertAccess()
        e.unit(PIXEL)
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("beamHeight1d")
        e.displayedName("Beam Height (1D Fit)")
        e.description("Beam heigth from 1D Fit. Defined as 4x sigma_y.")
        e.unit(Unit.METER).metricPrefix(MetricPrefix.MICRO)
        e.readOnly()
        e.commit()
        
        e = INT32_ELEMENT(expected).key("fitSuccess")
        e.displayedName("Success (2D Fit)")
        e.description("2-D Gaussian Fit Success (1-4 if fit converged).")
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("a2d")
        e.displayedName("A (2D Fit)")
        e.description("Amplitude A from 2D Fit.")
        e.unit(NUMBER)
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("x02d")
        e.displayedName("x0 (2D Fit)")
        e.description("x0 from 2D Fit.")
        e.unit(PIXEL)
        e.readOnly()
        e.commit()

        e = DOUBLE_ELEMENT(expected).key("ex02d")
        e.displayedName("sigma(x0) (2D Fit)")
        e.description("Uncertainty on x0 from 2D Fit.")
        e.expertAccess()
        e.unit(PIXEL)
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("sx2d")
        e.displayedName("sigma_x (2D Fit)")
        e.description("sigma_x from 2D Fit.")
        e.unit(PIXEL)
        e.readOnly()
        e.commit()

        e = DOUBLE_ELEMENT(expected).key("esx2d")
        e.displayedName("sigma(sigma_x) (2D Fit)")
        e.description("Uncertainty on sigma_x from 2D Fit.")
        e.expertAccess()
        e.unit(PIXEL)
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("beamWidth2d")
        e.displayedName("Beam Width (2D Fit)")
        e.description("Beam width from 2D Fit. Defined as 4x sigma_x.")
        e.unit(Unit.METER).metricPrefix(MetricPrefix.MICRO)
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("y02d")
        e.displayedName("y0 (2D Fit)")
        e.description("y0 from 2D Fit.")
        e.unit(PIXEL)
        e.readOnly()
        e.commit()

        e = DOUBLE_ELEMENT(expected).key("ey02d")
        e.displayedName("sigma(y0) (2D Fit)")
        e.description("Uncertainty on y0 from 2D Fit.")
        e.expertAccess()
        e.unit(PIXEL)
        e.readOnly()
        e.commit()

        e = DOUBLE_ELEMENT(expected).key("sy2d")
        e.displayedName("sigma_y (2D Fit)")
        e.description("sigma_y from 2D Fit.")
        e.unit(PIXEL)
        e.readOnly()
        e.commit()

        e = DOUBLE_ELEMENT(expected).key("esy2d")
        e.displayedName("sigma(sigma_y) (2D Fit)")
        e.description("Uncertainty on sigma_y from 2D Fit.")
        e.expertAccess()
        e.unit(PIXEL)
        e.readOnly()
        e.commit()

        e = DOUBLE_ELEMENT(expected).key("beamHeight2d")
        e.displayedName("Beam Height (2D Fit)")
        e.description("Beam height from 2D Fit. Defined as 4x sigma_y.")
        e.unit(Unit.METER).metricPrefix(MetricPrefix.MICRO)
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("theta2d")
        e.displayedName("theta (2D Fit)")
        e.description("Rotation angle from 2D Fit.")
        e.unit(DEGREE)
        e.readOnly()
        e.commit()

        e = DOUBLE_ELEMENT(expected).key("etheta2d")
        e.displayedName("sigma(theta) (2D Fit)")
        e.description("Uncertianty on rotation angle from 2D Fit.")
        e.expertAccess()
        e.unit(DEGREE)
        e.readOnly()
        e.commit()
    
    ##############################################
    #   Implementation of State Machine methods  #
    ##############################################

    def useAsBackgroundImage(self):
        self.log.INFO("Use current image as background.")
        self.bkgImage = numpy.array(self.currentImage)  # Copy current image to background image

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
    
    def onData(self, data):

        try:
            if isinstance(data, Data):
                # From Karabo 1.3.8 onData callback receives Data object as input
                if data.has('image'):
                    self.processImage(data['image'])
            elif isinstance(data, InputChannel):
                # Till Karabo 1.3.7 onData callback received InputChannel object as input
                for i in range(data.size()):
                    data_ = data.read(i)
                    if data_.has('image'):
                        self.processImage(data_['image'])

                # Signal that we are done with the current data
                data.update()
            else:
                raise ValueError("onData received wrong data type: %s" % type(data))

        except Exception as e:
            self.log.ERROR("Exception caught in onData: %s" % str(e))
    
    def onEndOfStream(self):
        self.log.INFO("onEndOfStream called")
    
    def processImage(self, image):
        filterImagesByThreshold = self.get("filterImagesByThreshold")
        imageThreshold = self.get("imageThreshold")
        range = self.get("fitRange")
        sigmas = self.get("rangeForAuto")
        thr = self.get("threshold")
        userDefinedRange = self.get("userDefinedRange")
        absolutePositions = self.get("absolutePositions")
        
        h = Hash() # Empty hash
        
        try:
            pixelSize = self.get("pixelSize")
        except:
            # No pixel size
            pixelSize = None
                
        try:
            imageArray = NDArray(image, copy=False)
            imageData = ImageData(image, copy=False)
            
            dims = imageData.getDimensions()
            imageWidth = dims[0]
            imageHeight = dims[1]
            h.set("imageWidth", imageWidth)
            h.set("imageHeight", imageHeight)

            try:
                roiOffsets = imageData.getROIOffsets()
                imageOffsetX = roiOffsets[0]
                imageOffsetY = roiOffsets[1]
            except:
                # Image has no ROI offset
                imageOffsetX = 0
                imageOffsetY = 0
            h.set("imageOffsetX", imageOffsetX)
            h.set("imageOffsetY", imageOffsetY)

            img = imageArray.getData() # data buffer will be converted to np.ndarray
            if img.ndim==3 and img.shape[0]==1:
                # Image has 3rd dimension, but it's 1
                self.log.DEBUG("Reshaping image...")
                img = img.squeeze()

            self.currentImage = numpy.array(img) # Copy current image, before doing any processing
            self.log.DEBUG("Image loaded!!!")
        
        except Exception as e:
            self.log.WARN("In processImage: %s" % str(e))
            return
        
        # Filter by Threshold
        if filterImagesByThreshold:
            if img.max()<imageThreshold:
                self.log.DEBUG("Max pixel value below threshold: image discared!!!")
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
            
            
            h.set("minMaxMeanTime", (t1-t0))
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
                self.log.WARN("Could not evaluate the pixel value frequency: %s." % str(e))
                return
            
            t1 = time.time()
            
            h.set("binCountTime", (t1-t0))
            h.set("imgBinCount", pxFreq)
        else:
            h.set("binCountTime", 0.0)
            h.set("imgBinCount", [0.0])


        # Background image subtraction
        if self.get("subtractBkgImage"):
            t0 = time.time()
            try:
                if self.bkgImage is not None and self.bkgImage.shape==img.shape:
                    # Subtract background image
                    m = (img>self.bkgImage)  # img is above bkg
                    n = (img<= self.bkgImage)  # image is below bkg

                    img[m] -= self.bkgImage[m] # subtract bkg from img, where img is above bkg
                    img[n] = 0 # zero img, where its is below bkg

            except Exception as e:
                self.log.WARN("Could not subtract background image: %s." % str(e))
                return

            t1 = time.time()

            h.set("subtractBkgImageTime", (t1-t0))
            self.log.DEBUG("Background image subtraction: done!")
        else:
            h.set("subtractBkgImageTime", 0.0)


        # Pedestal subtraction
        if self.get("subtractImagePedestal"):  # was "doBackground"
            t0 = time.time()
            try:
                imgMin = img.min()
                if imgMin>0:
                    # Subtract image pedestal
                    img = img-imgMin
            except Exception as e:
                self.log.WARN("Could not subtract image pedestal: %s." % str(e))
                return

            t1 = time.time()

            h.set("subtractPedestalTime", (t1-t0))  # was "backgroundTime"
            self.log.DEBUG("Image pedestal subtraction: done!")
        else:
            h.set("subtractPedestalTime", 0.0)  # was "backgroundTime"


        # Sum the image along the x- and y-axes
        imgX = None
        imgY = None
        if self.get("doXYSum"):
            t0 = time.time()
            try:
                imgX = image_processing.imageSumAlongY(img) # sum along y axis
                imgY = image_processing.imageSumAlongX(img) # sum along x axis

            except Exception as e:
                self.log.WARN("Could not sum image along x or y axis: %s." % str(e))
                return
            
            if imgX is None or imgY is None:
                self.log.WARN("Could not sum image along x or y axis.")
                return
            
            t1 = time.time()
            
            h.set("xYSumTime", (t1-t0))
            h.set("imgX", imgX)
            h.set("imgY", imgY)
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
                img2 = image_processing.imageSetThreshold(img, thr*img.max())
                
                # Centre-of-mass and widths
                (x0, y0, sx, sy) = image_processing.imageCentreOfMass(img2)
                
                if range=="full":
                    xmin = 0
                    xmax = imageWidth
                    ymin = 0
                    ymax = imageHeight
                elif range=="user-defined":
                    xmin = numpy.maximum(userDefinedRange[0], 0)
                    xmax = numpy.minimum(userDefinedRange[1], imageWidth)
                    ymin = numpy.maximum(userDefinedRange[2], 0)
                    ymax = numpy.minimum(userDefinedRange[3], imageHeight)
                    # TODO check that xmin<xmax and ymin<ymax
                else:
                    # "auto"
                    xmin = numpy.maximum(int(x0 - sigmas*sx), 0)
                    xmax = numpy.minimum(int(x0 + sigmas*sx), imageWidth)
                    ymin = numpy.maximum(int(y0 - sigmas*sy), 0)
                    ymax = numpy.minimum(int(y0 + sigmas*sy), imageHeight)
            
            except Exception as e:
                self.log.WARN("Could not calculate centre-of-mass: %s." % str(e))
                return
            
            t1 = time.time()
            
            h.set("cOfMTime", (t1-t0))
            if absolutePositions:
                h.set("x0", x0+imageOffsetX)
                h.set("y0", y0+imageOffsetY)
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
                if imgMin>0:
                    data -= data.min()

                # Initial parameters
                if None not in (self.ax1d, self.x01d, self.sx1d):
                    # Use last fit's parameters as initial estimate
                    p0 = (self.ax1d, self.x01d-xmin, self.sx1d)
                elif None not in (x0, sx):
                    # Use CoM for initial parameter estimate
                    p0 = (data.max(), x0-xmin, sx)
                else:
                    # No initial parameters
                    p0 = None

                # 1-d gaussian fit
                out = image_processing.fitGauss(data, p0)
                pX = out[0] # parameters
                cX = out[1] # covariance
                successX = out[2] # error

                # Save fit's parameters
                self.ax1d, self.x01d, self.sx1d = pX[0], pX[1]+xmin, pX[2]
                    
            except Exception as e:
                self.log.WARN("Could not do 1-d gaussian fit [x]: %s." % str(e))
                return
                
            t1 = time.time()
            
            try:
                if imgY is None:
                    imgY = image_processing.imageSumAlongX(img)
                
                # Select sub-range and substract pedestal
                data = imgY[ymin:ymax]
                imgMin = data.min()
                if imgMin>0:
                    data -= data.min()

                # Initial parameters
                if None not in (self.ay1d, self.y01d, self.sy1d):
                    # Use last fit's parameters as initial estimate
                    p0 = (self.ay1d, self.y01d-ymin, self.sy1d)
                elif None not in (y0, sy):
                    # Use CoM for initial parameter estimate
                    p0 = (data.max(), y0-ymin, sy)
                else:
                    # No initial parameters
                    p0 = None

                # 1-d gaussian fit
                out = image_processing.fitGauss(data, p0)
                pY = out[0] # parameters
                cY = out[1] # covariance
                successY = out[2] # error

                # Save fit's parameters
                self.ay1d, self.y01d, self.sy1d = pY[0], pY[1]+ymin, pY[2]

            except Exception as e:
                self.log.WARN("Could not do 1-d gaussian fit [y]: %s." % str(e))
                return
                
            t2 = time.time()
            
            h.set("xFitTime", (t1-t0))
            h.set("xFitSuccess", successX)
            if successX in (1, 2, 3, 4):
                # Successful fit
                if absolutePositions:
                    h.set("x01d", xmin+pX[1]+imageOffsetX)
                else:
                    h.set("x01d", xmin+pX[1])
                ex01d = math.sqrt(cX[1][1])
                h.set("ex01d", ex01d)
                h.set("sx1d", pX[2])
                esx1d = math.sqrt(cX[2][2])
                h.set("esx1d", esx1d)
                if pixelSize is not None:
                    beamWidth = self.stdDev2BeamSize * pixelSize * pX[2]
                    h.set("beamWidth1d", beamWidth)
            
            h.set("yFitTime", (t2-t1))
            h.set("yFitSuccess", successY)
            if successY in (1, 2, 3, 4):
                # Successful fit
                if absolutePositions:
                    h.set("y01d", ymin+pY[1]+imageOffsetY)
                else:
                    h.set("y01d", ymin+pY[1])
                ey01d = math.sqrt(cY[1][1])
                h.set("ey01d", ey01d)
                h.set("sy1d", pY[2])
                esy1d = math.sqrt(cY[2][2])
                h.set("esy1d", esy1d)
                if pixelSize is not None:
                    beamHeight = self.stdDev2BeamSize * pixelSize * pY[2]
                    h.set("beamHeight1d", beamHeight)
            
            if successX in (1, 2, 3, 4) and successY in (1, 2, 3, 4):
                ax1d = pX[0]/pY[2]/math.sqrt(2*math.pi)
                ay1d = pY[0]/pX[2]/math.sqrt(2*math.pi)
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
                if imgMin>0:
                    data -= data.min()

                if rotation:

                    # Initial parameters
                    if None not in (self.a2d, self.x02d, self.y02d, self.sx2d, self.sy2d, self.theta2d):
                        # Use last fit's parameters as initial estimate
                        p0 = (self.a2d, self.x02d-xmin, self.y02d-ymin, self.sx2d, self.sy2d, self.theta2d)
                    elif None not in (x0, y0, sx, sy):
                        # Use CoM for initial parameter estimate
                        p0 = (data.max(), x0-xmin, y0-ymin, sx, sy, 0.0)
                    else:
                        p0 = None

                    # 2-d gaussian fit
                    out = image_processing.fitGauss2DRot(data, p0)
                    pXY = out[0] # parameters: A, x0, y0, sx, sy, theta
                    cXY = out[1] # covariance
                    successXY = out[2] # error

                    # Save fit's parameters
                    self.a2d, self.x02d, self.y02d, self.sx2d, self.sy2d = pXY[0], pXY[1]+xmin, pXY[2]+ymin, pXY[3], pXY[4]
                    self.theta2d = pXY[5]

                else:

                    # Initial parameters
                    if None not in (self.a2d, self.x02d, self.y02d, self.sx2d, self.sy2d):
                        # Use last fit's parameters as initial estimate
                        p0 = (self.a2d, self.x02d-xmin, self.y02d-ymin, self.sx2d, self.sy2d)
                    elif None not in (x0, y0, sx, sy):
                        # Use CoM for initial parameter estimate
                        p0 = (data.max(), x0-xmin, y0-ymin, sx, sy)
                    else:
                        p0 = None

                    # 2-d gaussian fit
                    out = image_processing.fitGauss(data, p0)
                    pXY = out[0] # parameters: A, x0, y0, sx, sy
                    cXY = out[1] # covariance
                    successXY = out[2] # error

                    # Save fit's parameters
                    self.a2d, self.x02d, self.y02d, self.sx2d, self.sy2d = pXY[0], pXY[1]+xmin, pXY[2]+ymin, pXY[3], pXY[4]

            except Exception as e:
                self.log.WARN("Could not do 2-d gaussian fit: %s." % str(e))
                return
            
            t1 = time.time()
        
            h.set("fitTime", (t1-t0))
            h.set("fitSuccess", successXY)
            if successXY in (1, 2, 3, 4):
                h.set("a2d", pXY[0])
                # Successful fit
                if absolutePositions:
                    h.set("x02d", xmin+pXY[1]+imageOffsetX)
                    h.set("y02d", ymin+pXY[2]+imageOffsetY)
                else:
                    h.set("x02d", xmin+pXY[1])
                    h.set("y02d", ymin+pXY[2])
                h.set("ex02d", math.sqrt(cXY[1][1]))
                h.set("ey02d", math.sqrt(cXY[2][2]))
                h.set("sx2d", pXY[3])
                h.set("sy2d", pXY[4])
                h.set("esx2d", math.sqrt(cXY[3][3]))
                h.set("esy2d", math.sqrt(cXY[4][4]))
                if pixelSize is not None:
                    beamWidth = self.stdDev2BeamSize * pixelSize * pXY[3]
                    h.set("beamWidth2d", beamWidth)
                    beamHeight = self.stdDev2BeamSize * pixelSize * pXY[4]
                    h.set("beamHeight2d", beamHeight)
                if rotation:
                    h.set("theta2d", pXY[5]%math.pi)
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
