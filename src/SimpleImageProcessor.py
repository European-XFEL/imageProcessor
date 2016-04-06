__author__="andrea.parenti@xfel.eu"
__date__ ="April  6, 2016, 12:28 PM"
__copyright__="Copyright (c) 2010-2016 European XFEL GmbH Hamburg. All rights reserved."

import math
import numpy
import time

from karabo.decorators import KARABO_CLASSINFO
from karabo.device import PythonDevice, launchPythonDevice
from karabo.ok_error_fsm import OkErrorFsm
from karabo.karathon import (
    BOOL_ELEMENT, DOUBLE_ELEMENT, FLOAT_ELEMENT, IMAGEDATA, INPUT_CHANNEL,
    INT32_ELEMENT, OVERWRITE_ELEMENT,
    Data, Hash, ImageData, InputChannel, MetricPrefix, NDArray, Schema, Unit
)

from image_processing import image_processing


@KARABO_CLASSINFO("SimpleImageProcessor", "1.3 1.4")
class SimpleImageProcessor(PythonDevice, OkErrorFsm):

    # Numerical factor to convert gaussian standard deviation to beam size
    stdDev2BeamSize = 4.0

    def __init__(self, configuration):
        # always call superclass constructor first!
        super(SimpleImageProcessor,self).__init__(configuration)

        # 1d gaussian fit parameters
        self.ax1d = None
        self.x01d = None
        self.sx1d = None
        self.ay1d = None
        self.y01d = None
        self.sy1d = None

        # Current image
        self.currentImage = None

        # frames per second
        self.lastTime = None
        self.counter = 0

    def __del__(self):
        super(SimpleImageProcessor, self).__del__()

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

        # Images should be dropped if processor is too slow
        OVERWRITE_ELEMENT(expected).key("input.onSlowness")
                .setNewDefaultValue("drop")
                .commit(),
        )

        (
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
                .description("The image offset in X direction, i.e. the X "
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

        # Processor configuration

        FLOAT_ELEMENT(expected).key("pixelSize")
                .displayedName("Pixel Size")
                .description("The pixel size.")
                .assignmentOptional().noDefaultValue()
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
                .init()
                .commit(),
        
        FLOAT_ELEMENT(expected).key("fitRange")
                .displayedName("Fit Range")
                .description("The range for the gaussian fit (in standard "
                             "deviations).")
                .assignmentOptional().defaultValue(3.0)
                .init()
                .commit(),
        
        FLOAT_ELEMENT(expected).key("pixelThreshold")
                .displayedName("Pixel Relative threshold")
                .description("The pixel threshold for centre-of-gravity "
                             "calculation (fraction of highest value). Pixels "
                             "below threshold will be discarded.")
                .assignmentOptional().defaultValue(0.10)
                .minInc(0.0).maxInc(1.0)
                .init()
                .commit(),

        BOOL_ELEMENT(expected).key("subtractImagePedestal")
                .displayedName("Subtract Image Pedestal")
                .description("Subtract the image pedestal (ie image = image - "
                             "image.min()) before centre-of-mass and gaussian "
                             "fit.")
                .assignmentOptional().defaultValue(True)
                .init()
                .commit(),
        
        # Image processing outputs
        
        DOUBLE_ELEMENT(expected).key("maxPxValue")
                .displayedName("Max Pixel Value")
                .description("Maximun pixel value.")
                .unit(Unit.NUMBER)
                .readOnly()
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
                .description("Beam heigth from 1D Fit. Defined as 4x sigma_y.")
                .unit(Unit.METER).metricPrefix(MetricPrefix.MICRO)
                .readOnly()
                .commit(),
        )

    
    ##############################################
    #   Implementation of State Machine methods  #
    ##############################################

    def okStateOnEntry(self):
        
        # Register call-backs
        self.KARABO_ON_DATA("input", self.onData)
        self.KARABO_ON_EOS("input", self.onEndOfStream)

        h = Hash()

        h.set("maxPxValue", 0.0)
        h.set("x0", 0.0)
        h.set("sx", 0.0)
        h.set("y0", 0.0)
        h.set("sy", 0.0)
        h.set("ax1d", 0.0)
        h.set("x01d", 0.0)
        h.set("ex01d", 0.0)
        h.set("sx1d", 0.0)
        h.set("esx1d", 0.0)
        h.set("beamWidth1d", 0.0)
        h.set("ay1d", 0.0)
        h.set("y01d", 0.0)
        h.set("ey01d", 0.0)
        h.set("sy1d", 0.0)
        h.set("esy1d", 0.0)
        h.set("beamHeight1d", 0.0)
    
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
        imageThreshold = self.get("imageThreshold")
        fitRange = self.get("fitRange")
        pixelThreshold = self.get("pixelThreshold")
        
        h = Hash() # Empty hash

        try:
            self.counter += 1
            currentTime = time.time()
            if self.lastTime is None:
                self.counter = 0
                self.lastTime = currentTime
            elif self.lastTime is not None and (currentTime-self.lastTime)>1.:
                fps = self.counter / (currentTime-self.lastTime)
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
        if img.max()<imageThreshold:
            self.log.DEBUG("Max pixel value below threshold: image discared!!!")
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
                if imgMin>0:
                    # Subtract image pedestal
                    img = img-imgMin
            except Exception as e:
                self.log.WARN("Could not subtract image pedestal: %s." % str(e))
                return

            self.log.DEBUG("Image pedestal subtraction: done!")

        # Centre-Of-Mass and widths
        try:
            # Set a threshold to cut away noise
            img2 = image_processing.imageSetThreshold(img, pixelThreshold*img.max())
            
            # Centre-of-mass and widths
            (x0, y0, sx, sy) = image_processing.imageCentreOfMass(img2)
            
            xmin = numpy.maximum(int(x0 - fitRange*sx), 0)
            xmax = numpy.minimum(int(x0 + fitRange*sx), imageWidth)
            ymin = numpy.maximum(int(y0 - fitRange*sy), 0)
            ymax = numpy.minimum(int(y0 + fitRange*sy), imageHeight)
            
            h.set("x0", x0+imageOffsetX)
            h.set("y0", y0+imageOffsetY)
            h.set("sx", sx)
            h.set("sy", sy)

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
                            
        try:
            # Sum image along x axis
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
                
        if successX in (1, 2, 3, 4):
            # Successful fit
            h.set("x01d", xmin+pX[1]+imageOffsetX)
            ex01d = math.sqrt(cX[1][1])
            h.set("ex01d", ex01d)
            h.set("sx1d", pX[2])
            esx1d = math.sqrt(cX[2][2])
            h.set("esx1d", esx1d)
            if pixelSize is not None:
                beamWidth = self.stdDev2BeamSize * pixelSize * pX[2]
                h.set("beamWidth1d", beamWidth)
        
        if successY in (1, 2, 3, 4):
            # Successful fit
            h.set("y01d", ymin+pY[1]+imageOffsetY)
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


        # Update device parameters (all at once)
        self.set(h)
        
if __name__ == "__main__":
    launchPythonDevice()
