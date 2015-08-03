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
        
    def __del__(self):
        super(ImageProcessor, self).__del__()

    @staticmethod
    def expectedParameters(expected):
        data = Schema()

        (
        IMAGEDATA(data).key("image")
        .commit(),

        INPUT_CHANNEL(expected).key("input")
                .displayedName("Input")
                .dataSchema(data)
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
        
        e = BOOL_ELEMENT(expected).key("doBackground")
        e.displayedName("Subtract Background")
        e.description("Subtract the background.")
        e.assignmentOptional().defaultValue(True)
        e.reconfigurable()
        e.commit()
        
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
        
        e = BOOL_ELEMENT(expected).key("doProjection")
        e.displayedName("X-Y Projections")
        e.description("Project the image onto the x- and y-axes.")
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
        e.description("Perform a 1-d gaussian fit of the x- and y-projections.")
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
        
        e = FLOAT_ELEMENT(expected).key("backgroundTime")
        e.displayedName("Background Subtraction Time")
        e.unit(SECOND)
        e.readOnly()
        e.commit()
        
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
        
        e = FLOAT_ELEMENT(expected).key("projectionTime")
        e.displayedName("Image Projection Time")
        e.unit(SECOND)
        e.readOnly()
        e.commit()
        
        e = FLOAT_ELEMENT(expected).key("cOfMTime")
        e.displayedName("Centre-Of-Mass Time")
        e.unit(SECOND)
        e.readOnly()
        e.commit()
        
        e = FLOAT_ELEMENT(expected).key("xFitTime")
        e.displayedName("1D Gaussian Fit Time (X projection)")
        e.unit(SECOND)
        e.readOnly()
        e.commit()
        
        e = FLOAT_ELEMENT(expected).key("yFitTime")
        e.displayedName("1D Gaussian Fit Time (Y projection)")
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
        e.displayedName("Image x-projection")
        e.description("Projection of the input image onto the x axis.")
        e.readOnly().initialValue([0])
        e.commit()
        
        e = VECTOR_DOUBLE_ELEMENT(expected).key("imgY")
        e.displayedName("Image y-projection")
        e.description("Projection of the input image onto the y axis.")
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
        
        e = DOUBLE_ELEMENT(expected).key("sx1d")
        e.displayedName("sigma_x (1D Fit)")
        e.description("sigma_x from 1D Fit.")
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
        
        e = DOUBLE_ELEMENT(expected).key("sy1d")
        e.displayedName("sigma_y (1D Fit)")
        e.description("sigma_y from 1D Fit.")
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
        
        e = DOUBLE_ELEMENT(expected).key("sx2d")
        e.displayedName("sigma_x (2D Fit)")
        e.description("sigma_x from 2D Fit.")
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
        
        e = DOUBLE_ELEMENT(expected).key("sy2d")
        e.displayedName("sigma_y (2D Fit)")
        e.description("sigma_y from 2D Fit.")
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
        
    
    ##############################################
    #   Implementation of State Machine methods  #
    ##############################################

    def okStateOnEntry(self):
        
        # Register call-backs
        self.KARABO_ON_DATA("input", self.onData)
        self.KARABO_ON_EOS("input", self.onEndOfStream)

        h = Hash()

        h.set("minMaxMeanTime", 0.0)
        h.set("binCountTime", 0.0)
        h.set("projectionTime", 0.0)
        h.set("xFitTime", 0.0)
        h.set("yFitTime", 0.0)
        h.set("cOfMTime", 0.0)
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
        h.set("sx1d", 0.0)
        h.set("beamWidth1d", 0.0)
        h.set("yFitSuccess", 0)
        h.set("ay1d", 0.0)
        h.set("y01d", 0.0)
        h.set("sy1d", 0.0)
        h.set("beamHeight1d", 0.0)
        h.set("fitSuccess", 0)
        h.set("a2d", 0.0)
        h.set("x02d", 0.0)
        h.set("sx2d", 0.0)
        h.set("beamWidth2d", 0.0)
        h.set("y02d", 0.0)
        h.set("sy2d", 0.0)
        h.set("theta2d", 0.0)
        h.set("beamHeight2d", 0.0)
    
        # Reset device parameters (all at once)
        self.set(h)

#    # [AP] Till Karabo 1.3.7 onData callback received InputChannel object as input
#    def onData(self, input):
#        
#        try:
#            for i in range(input.size()):
#                data = input.read(i)
#                if data.has('image'):
#                    self.processImage(data['image'])
#    
#            # Signal that we are done with the current data
#            input.update()
#        
#        except Exception as e:
#            self.log.ERROR("Exception caught in onData: %s" % str(e))
    
    # [AP] From Karabo 1.3.8 onData callback receives Data object as input
    def onData(self, data):
        
        try:
            if data.has('image'):
                self.processImage(data['image'])
        except Exception as e:
            self.log.ERROR("Exception caught in onData: %s" % str(e))
    
    def onEndOfStream(self):
        print("onEndOfStream called")
    
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
            imageArray = NDArray(image)
            imageData = ImageData(image)
            
            dims = imageData.getDimensions()
            imageWidth = dims[0]
            imageHeight = dims[1]
            h.set("imageWidth", imageWidth)
            h.set("imageHeight", imageHeight)
            
            roiOffsets = imageData.getROIOffsets()
            imageOffsetX = roiOffsets[0]
            imageOffsetY = roiOffsets[1]
            h.set("imageOffsetX", imageOffsetX)
            h.set("imageOffsetY", imageOffsetY)

            img = imageArray.getData()
            if img.ndim==3 and img.shape[0]==1:
                # Image has 3rd dimension, but it's 1
                self.log.DEBUG("Reshaping image...")
                img = img.reshape((img.shape[1], img.shape[2]))
            
            self.log.DEBUG("Image loaded!!!")
        
        except Exception as e:
            self.log.WARN("In processImage: %s" % str(e))
            return
        
        # Filter by Threshold
        if filterImagesByThreshold:
            if img.max()<imageThreshold:
                self.log.DEBUG("Max pixel value below threshold: image discared!!!")
                return
        
        # "Background" subtraction
        if self.get("doBackground"):
            t0 = time.time()
            try:
                img = img-img.min()
            except:
                self.log.WARN("Could not subtract background.")
                return
                
            t1 = time.time()
                
            
            h.set("backgroundTime", (t1-t0))
            self.log.DEBUG("Background subtraction: done!")
        else:
            h.set("backgroundTime", 0.0)
        
        
        # Get pixel min/max/mean values
        if self.get("doMinMaxMean"):
            t0 = time.time()
            try:
                imgMin = img.min()
                imgMax = img.max()
                imgMean = img.mean()
            except:
                self.log.WARN("Could not read min, max, mean.")
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
            except:
                self.log.WARN("Could not evaluate the pixel value frequency.")
                return
            
            t1 = time.time()
            
            h.set("binCountTime", (t1-t0))
            h.set("imgBinCount", pxFreq)
        else:
            h.set("binCountTime", 0.0)
            h.set("imgBinCount", [0.0])
        
        
        # Project the image onto the x- and y-axes
        imgX = None
        imgY = None
        if self.get("doProjection"):
            t0 = time.time()
            try:
                imgX = image_processing.imageXProjection(img) # projection onto the x-axis
                imgY = image_processing.imageYProjection(img) # projection onto the y-axis

            except:
                self.log.WARN("Could not project image into x or y axis.")
                return
            
            if imgX is None or imgY is None:
                self.log.WARN("Could not project image into x or y axis.")
                return
            
            t1 = time.time()
            
            h.set("projectionTime", (t1-t0))
            h.set("imgX", imgX)
            h.set("imgY", imgY)
            self.log.DEBUG("Image 1D projections: done!")
        else:
            h.set("projectionTime", 0.0)
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
            
            except:
                self.log.WARN("Could not calculate centre-of-mass.")
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
                if imgX==None:
                    imgX = image_processing.imageXProjection(img)
                
                # Select sub-range and substract pedestal
                data = imgX[xmin:xmax]
                data = data - data.min()

                if x0!=None and sx!=None:
                    # Initial parameters
                    p0 = (data.max(), x0-xmin, sx)

                    # 1-d gaussian fit
                    pX, successX = image_processing.fitGauss(data, p0)
                else:
                    pX, successX = image_processing.fitGauss(data)
                    
            except:
                self.log.WARN("Could not do 1-d gaussian fit.")
                return
                
            t1 = time.time()
            
            try:
                if imgY==None:
                    imgY = image_processing.imageYProjection(img)
                
                # Select sub-range and substract pedestal
                data = imgY[ymin:ymax]
                data = data - data.min()
                
                if y0!=None and sy!=None:
                    # Initial parameters
                    p0 = (data.max(), y0-ymin, sx)
                    
                    # 1-d gaussian fit
                    pY, successY = image_processing.fitGauss(data, p0)
                else:
                    pY, successY = image_processing.fitGauss(data)
                    
            except:
                self.log.WARN("Could not do 1-d gaussian fit.")
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
                h.set("sx1d", pX[2])
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
                h.set("sy1d", pY[2])
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
            h.set("sx1d", 0.0)
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
                data = data - data.min()

                if rotation:
                    if x0!=None and y0!=None and sx!=None and sy!=None:
                        # Initial parameters
                        p0 = (data.max(), y0-ymin, x0-xmin, sy, sx, 0.0)
                        
                        # 2-d gaussian fit
                        pYX, successYX = image_processing.fitGauss2DRot(data, p0)
                    else:
                        pYX, successYX = fitGauss2DRot(data)

                else:
                    if x0!=None and y0!=None and sx!=None and sy!=None:
                        # Initial parameters
                        p0 = (data.max(), y0-ymin, x0-xmin, sy, sx)
                        
                        # 2-d gaussian fit
                        pYX, successYX = image_processing.fitGauss(data, p0)
                    else:
                        pYX, successYX = image_processing.fitGauss(data)
                    
            except:
                self.log.WARN("Could not do 2-d gaussian fit.")
                return
            
            t1 = time.time()
        
            h.set("fitTime", (t1-t0))
            h.set("fitSuccess", successYX)
            if successY in (1, 2, 3, 4):
                h.set("a2d", pYX[0])
                # Successful fit
                if absolutePositions:
                    h.set("x02d", xmin+pYX[2]+imageOffsetX)
                    h.set("y02d", ymin+pYX[1]+imageOffsetY)
                else:
                    h.set("x02d", xmin+pYX[2])
                    h.set("y02d", ymin+pYX[1])
                h.set("sx2d", pYX[4])
                h.set("sy2d", pYX[3])
                if pixelSize is not None:
                    beamWidth = self.stdDev2BeamSize * pixelSize * pYX[4]
                    h.set("beamWidth2d", beamWidth)
                    beamHeight = self.stdDev2BeamSize * pixelSize * pYX[3]
                    h.set("beamHeight2d", beamHeight)
                if rotation:
                    h.set("theta2d", pYX[5]%math.pi)
                else:
                    h.set("theta2d", 0.0)
            
            self.log.DEBUG("2-d gaussian fit: done!")
        else:
            h.set("fitTime", 0.0)
            h.set("fitSuccess", 0)
            h.set("a2d", 0.0)
            h.set("x02d", 0.0)
            h.set("sx2d", 0.0)
            h.set("beamWidth2d", 0.0)
            h.set("y02d", 0.0)
            h.set("sy2d", 0.0)
            h.set("beamHeight2d", 0.0)
            h.set("theta2d", 0.0)
    
        # Update device parameters (all at once)
        self.set(h)
        
if __name__ == "__main__":
    launchPythonDevice()
