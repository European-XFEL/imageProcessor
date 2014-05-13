#!/usr/bin/env python

# TODO: display 1d and 2d fits

__author__="andrea.parenti@xfel.eu"
__date__ ="October 10, 2013, 10:29 AM"
__copyright__="Copyright (c) 2010-2013 European XFEL GmbH Hamburg. All rights reserved."

import numpy
import time

from karabo.compute_device import *

import image_processing

@KARABO_CLASSINFO("ImageProcessor", "1.0 1.1")
class ImageProcessor(PythonComputeDevice):

    def __init__(self, configuration):
        # always call superclass constructor first!
        super(ImageProcessor,self).__init__(configuration)
        self.input = self.KARABO_INPUT_CHANNEL(InputHash, "input", configuration)
        
    def __del__(self):
        print "**** ImageProcessor.__del__() use_count =", self.input.use_count()
        self.input = None
        self.log.INFO("dead.")
        super(ImageProcessor, self).__del__()

    
    
    @staticmethod
    def expectedParameters(expected):
        e = CHOICE_ELEMENT(expected).key("input")
        e.displayedName("Input")
        e.description("Input")
        e.assignmentOptional().defaultValue("Network-Hash")
        e.appendNodesOfConfigurationBase(InputHash)
        e.commit()
        
        e = IMAGE_ELEMENT(expected).key("image")
        e.displayedName("Image")
        e.description("Image")
        e.commit()

        e = INT32_ELEMENT(expected).key("imageWidth")
        e.displayedName("Image Width")
        e.description("The image width.")
        e.unit(PIXEL)
        e.readOnly()
        e.commit()
        
        e = INT32_ELEMENT(expected).key("imageHeight")
        e.displayedName("Image Height")
        e.description("The image height.")
        e.unit(PIXEL)
        e.readOnly()
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
        e.assignmentOptional().defaultValue(True)
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
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("maxPxValue")
        e.displayedName("Max Pixel Value")
        e.description("Maximun pixel value.")
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("meanPxValue")
        e.displayedName("Mean Pixel Value")
        e.description("Mean pixel value.")
        e.readOnly()
        e.commit()
        
        e = VECTOR_DOUBLE_ELEMENT(expected).key("imgBinCount")
        e.displayedName("Pixel counts distribution")
        e.description("Distribution of the image pixel counts.")
        e.readOnly()
        e.commit()
        
        e = VECTOR_DOUBLE_ELEMENT(expected).key("imgX")
        e.displayedName("Image x-projection")
        e.description("Projection of the input image onto the x axis.")
        e.readOnly()
        e.commit()
        
        e = VECTOR_DOUBLE_ELEMENT(expected).key("imgY")
        e.displayedName("Image y-projection")
        e.description("Projection of the input image onto the y axis.")
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("x0")
        e.displayedName("x0 (Centre-Of-Mass)")
        e.description("x0 from centre-of-mass.")
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("sx")
        e.displayedName("sigma_x (Centre-Of-Mass)")
        e.description("sigma_x from centre-of-mass.")
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("y0")
        e.displayedName("y0 (Centre-Of-Mass)")
        e.description("y0 from Centre-Of-Mass.")
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("sy")
        e.displayedName("sigma_y (Centre-Of-Mass)")
        e.description("sigma_y from Centre-Of-Mass.")
        e.readOnly()
        e.commit()
        
        e = INT32_ELEMENT(expected).key("xFitSuccess")
        e.displayedName("x Success (1D Fit)")
        e.description("1-D Gaussian Fit Success (1-4 if fit converged).")
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("x01d")
        e.displayedName("x0 (1D Fit)")
        e.description("x0 from 1D Fit.")
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("sx1d")
        e.displayedName("sigma_x (1D Fit)")
        e.description("sigma_x from 1D Fit.")
        e.readOnly()
        e.commit()
        
        e = INT32_ELEMENT(expected).key("yFitSuccess")
        e.displayedName("y Success (1D Fit)")
        e.description("1-D Gaussian Fit Success (1-4 if fit converged).")
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("y01d")
        e.displayedName("y0 (1D Fit)")
        e.description("y0 from 1D Fit.")
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("sy1d")
        e.displayedName("sigma_y (1D Fit)")
        e.description("sigma_y from 1D Fit.")
        e.readOnly()
        e.commit()
                
        e = INT32_ELEMENT(expected).key("fitSuccess")
        e.displayedName("Success (2D Fit)")
        e.description("2-D Gaussian Fit Success (1-4 if fit converged).")
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("x02d")
        e.displayedName("x0 (2D Fit)")
        e.description("x0 from 2D Fit.")
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("sx2d")
        e.displayedName("sigma_x (2D Fit)")
        e.description("sigma_x from 2D Fit.")
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("y02d")
        e.displayedName("y0 (2D Fit)")
        e.description("y0 from 2D Fit.")
        e.readOnly()
        e.commit()
        
        e = DOUBLE_ELEMENT(expected).key("sy2d")
        e.displayedName("sigma_y (2D Fit)")
        e.description("sigma_y from 2D Fit.")
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

    def initializationStateOnEntry(self):
        self.set("minMaxMeanTime", 0.0)
        self.set("binCountTime", 0.0)
        self.set("projectionTime", 0.0)
        self.set("xFitTime", 0.0)
        self.set("yFitTime", 0.0)
        self.set("cOfMTime", 0.0)
        self.set("fitTime", 0.0)

        self.set("minPxValue", 0.0)
        self.set("maxPxValue", 0.0)
        self.set("meanPxValue", 0.0)
        self.set("x0", 0.0)
        self.set("sx", 0.0)
        self.set("y0", 0.0)
        self.set("sy", 0.0)
        self.set("xFitSuccess", 0)
        self.set("x01d", 0.0)
        self.set("sx1d", 0.0)
        self.set("yFitSuccess", 0)
        self.set("y01d", 0.0)
        self.set("sy1d", 0.0)
        self.set("fitSuccess", 0)
        self.set("x02d", 0.0)
        self.set("sx2d", 0.0)
        self.set("y02d", 0.0)
        self.set("sy2d", 0.0)
        self.set("theta2d", 0.0)
        
    
    def compute(self):
        h = Hash()
        
        for i in range(0, self.input.size()):
            self.input.read(h, i)
            
            if (h.has("image")):
                self.log.INFO("New image received")
                image = h.get("image")

                self.processImage(image)
    
    def processImage(self, image):
        range = self.get("fitRange")
        sigmas = self.get("rangeForAuto")
        thr = self.get("threshold")
        userDefinedRange = self.get("userDefinedRange")
        
        try:
            
            rawImageData = RawImageData(image)
            self.set("image", rawImageData)
            
            dims = rawImageData.getDimensions()
            imageWidth = dims[0]
            imageHeight = dims[1]
            self.set("imageWidth", imageWidth)
            self.set("imageHeight", imageHeight)
            
            img = image_processing.rawImageDataToNdarray(rawImageData)
            
            self.log.INFO("Image loaded!!!")
        
        except Exception, e:
            self.log.WARN("In processImage: %s" % str(e))
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
                
            
            self.set("backgroundTime", (t1-t0))
            self.log.INFO("Background subtraction: done!")
        else:
            self.set("backgroundTime", 0.0)
        
        
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
            
            
            self.set("minMaxMeanTime", (t1-t0))
            self.set("minPxValue", float(imgMin))
            self.set("maxPxValue", float(imgMax))
            self.set("meanPxValue", float(imgMean))
            self.log.INFO("Pixel min/max/mean: done!")
        else:
            self.set("minMaxMeanTime", 0.0)
            self.set("minPxValue", 0.0)
            self.set("maxPxValue", 0.0)
            self.set("meanPxValue", 0.0)
        
        
        # Frequency of Pixel Values
        if self.get("doBinCount"):
            t0 = time.time()
            try:
                pxFreq = image_processing.imagePixelValueFrequencies(img)

                self.log.INFO("Pixel values distribution: done!")
            except:
                self.log.WARN("Could not evaluate the pixel value frequency.")
                return
            
            t1 = time.time()
            
            self.set("binCountTime", (t1-t0))
            self.set("imgBinCount", pxFreq)
        else:
            self.set("binCountTime", 0.0)
            self.set("imgBinCount", [0.0])
        
        
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
                
            t1 = time.time()
            
            self.set("projectionTime", (t1-t0))
            self.set("imgX", imgX)
            self.set("imgY", imgY)
            self.log.INFO("Image 1D projections: done!")
        else:
            self.set("projectionTime", 0.0)
            self.set("imgX", [0.0])
            self.set("imgY", [0.0])
            
        
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
            
            self.set("cOfMTime", (t1-t0))
            self.set("x0", x0)
            self.set("sx", sx)
            self.set("y0", y0)
            self.set("sy", sy)
            self.log.INFO("Centre-of-mass and widths: done!")  
        
        else:
            self.set("cOfMTime", 0.0)
            self.set("x0", 0.0)
            self.set("sx", 0.0)
            self.set("y0", 0.0)
            self.set("sx", 0.0)
        
        
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
        
            self.set("xFitTime", (t1-t0))
            self.set("yFitTime", (t2-t1))
            self.set("xFitSuccess", successX)
            self.set("x01d", xmin+pX[1])
            self.set("sx1d", pX[2])
            self.set("yFitSuccess", successY)
            self.set("y01d", ymin+pY[1])
            self.set("sy1d", pY[2])
            self.log.INFO("1-d gaussian fit: done!")
        else:
            self.set("xFitTime", 0.0)
            self.set("yFitTime", 0.0)
            self.set("xFitSuccess", 0)
            self.set("x01d", 0.0)
            self.set("sx1d", 0.0)
            self.set("yFitSuccess", 0)
            self.set("y01d", 0.0)
            self.set("sy1d", 0.0)
            
        
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
        
            self.set("fitTime", (t1-t0))
            self.set("fitSuccess", successYX)
            self.set("x02d", xmin+pYX[2])
            self.set("sx2d", pYX[4])
            self.set("y02d", ymin+pYX[1])
            self.set("sy2d", pYX[3])
            if rotation:
                self.set("theta2d", pYX[5])
            else:
                self.set("theta2d", 0.0)
            self.log.INFO("2-d gaussian fit: done!")
        else:
            self.set("fitTime", 0.0)
            self.set("fitSuccess", 0)
            self.set("x02d", 0.0)
            self.set("sx2d", 0.0)
            self.set("y02d", 0.0)
            self.set("sy2d", 0.0)
            self.set("theta2d", 0.0)
    
        
if __name__ == "__main__":
    launchPythonDevice()
