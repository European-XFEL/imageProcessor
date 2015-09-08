#!/usr/bin/env python

__author__="andrea.parenti@xfel.eu"
__date__ ="May  9, 2014, 17:01 AM"
__copyright__="Copyright (c) 2010-2014 European XFEL GmbH Hamburg. All rights reserved."

import numpy
import scipy.constants

from karabo.device import *
from karabo.ok_error_fsm import OkErrorFsm

from image_processing import image_processing

@KARABO_CLASSINFO("AutoCorrelator", "1.3")
class AutoCorrelator(PythonDevice, OkErrorFsm):

    def __init__(self, configuration):
        # always call superclass constructor first!
        super(AutoCorrelator,self).__init__(configuration)
        
        self._ss.registerSlot(self.useAsCalibrationImage1)
        self._ss.registerSlot(self.useAsCalibrationImage2)
        self._ss.registerSlot(self.calibrate)
        
        self.currentPeak = None
        self.currentFwhm = None
        
    def __del__(self):
        super(AutoCorrelator, self).__del__()

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
        
        (
        DOUBLE_ELEMENT(expected)
                .key("xPeak1")
                .displayedName("Image1 Peak (x)")
                .description("x-position of peak in first calibration image.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),
        
        DOUBLE_ELEMENT(expected)
                .key("xFWHM1")
                .displayedName("Image1 FWHM (x)")
                .description("x-FWHM in first calibration image.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),
        
        DOUBLE_ELEMENT(expected)
                .key("xPeak2")
                .displayedName("Image2 Peak (x)")
                .description("x-position of peak in second calibration image.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),
        
        DOUBLE_ELEMENT(expected)
                .key("xFWHM2")
                .displayedName("Image2 FWHM (x)")
                .description("x-FWHM in second calibration image.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),
        
        STRING_ELEMENT(expected)
                .key("delayUnit")
                .displayedName("Delay Unit")
                .description("Unit of the delay between calibration images.")
                .assignmentOptional().defaultValue("fs")
                .options("fs um")
                .reconfigurable()
                .allowedStates("Ok")
                .commit(),
        
        DOUBLE_ELEMENT(expected)
                .key("delay")
                .displayedName("Delay ([fs] or [um])")
                .description("Delay between calibration images.")
                .assignmentOptional().defaultValue(0)
                .reconfigurable()
                .allowedStates("Ok")
                .commit(),
        
        SLOT_ELEMENT(expected).key("useAsCalibrationImage1")
                .displayedName("Current Image as 1st Calibration")
                .description("Use the current image as 1st calibration image.")
                .commit(),

        SLOT_ELEMENT(expected).key("useAsCalibrationImage2")
                .displayedName("Current Image as 2nd Calibration")
                .description("Use the current image as 2nd calibration image.")
                .commit(),
        
        SLOT_ELEMENT(expected).key("calibrate")
                .displayedName("Calibrate")
                .description("Calculate calibration constant from two input images.")
                .allowedStates("Ok")
                .commit(),
        
        DOUBLE_ELEMENT(expected)
                .key("calibrationFactor")
                .displayedName("Calibration constant [fs/px]")
                .description("The calibration constant.")
                # .unit(Unit.???) # TODO Unit is fs/px
                .assignmentOptional().defaultValue(0)
                .reconfigurable()
                .allowedStates("Ok")
                .commit(),
        
        DOUBLE_ELEMENT(expected)
                .key("shapeFactor")
                .displayedName("Shape Factor")
                .description("Shape factor to convert FWHM to peak width.")
                .assignmentOptional().defaultValue(1.)
                # .options("1.") # TODO...
                .reconfigurable()
                .allowedStates("Ok")
                .commit(),
        
        DOUBLE_ELEMENT(expected)
                .key("xPeak3")
                .displayedName("Input Image Peak (x)")
                .description("x-position of peak in the input image.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),
        
        DOUBLE_ELEMENT(expected)
                .key("xFWHM3")
                .displayedName("Input Image FWHM (x)")
                .description("x-FWHM in the input image.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),
        
        DOUBLE_ELEMENT(expected)
                .key("xWidth3")
                .displayedName("Input Image Peak Width")
                .description("x-Width of the input image.")
                .unit(Unit.SECOND).metricPrefix(MetricPrefix.FEMTO)
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
    
    def preReconfigure(self, inputConfig):
        self.log.INFO("preReconfigure")
        
        recalculateWidth = False
        calibrationFactor = self.get("calibrationFactor")
        shapeFactor = self.get("shapeFactor")
        
        if inputConfig.has("calibrationFactor"):
            # Calibration factor has changed
            calibrationFactor = inputConfig.get("calibrationFactor")
            recalculateWidth = True
        
        if inputConfig.has("shapeFactor"):
            # Shape factor has changed
            shapeFactor = inputConfig.get("shapeFactor")
            recalculateWidth = True
        
        if recalculateWidth is True and self.currentFwhm is not None:
            w3 = self.currentFwhm * shapeFactor * calibrationFactor
            self.set("xWidth3", w3)
            self.log.DEBUG("Image re-processed!!!")
    
    def calibrate(self):
        '''Calculate calibration constant'''
        
        self.log.INFO("Calibrating auto-correlator...")
        
        try:
            delayUnit = self["delayUnit"]
            if delayUnit=="fs":
                delay = self["delay"]
            elif delayUnit=="um":
                # Must convert to time
                delay = 1e+9 * self["delay"] / scipy.constants.c
            else:
                errorFound("Unknown delay unit #s" % delayUnit, "")

            dX = self["xPeak1"] - self["xPeak2"]
            if dX==0:
                self.errorFound("Same peak position for the two images", "")

            calibrationFactor = abs(delay / dX)
            self.set("calibrationFactor", calibrationFactor)
            
        except:
            self.errorFound("Cannot calculate calibration constant", "")
    
    def findPeakFWHM(self, image, threshold=0.5):
        """Find x-position of peak in 2-d image, and FWHM along x direction"""
        if not isinstance(image, numpy.ndarray) or image.ndim!=2:
            return None

        ### First work on y distribution ###

        # sum along X
        imgY = image_processing.imageSumAlongX(image)

        # Threshold level
        thr = threshold*imgY.max()

        # Find 1st and last point above threshold
        nz = numpy.flatnonzero(imgY>thr)
        y1 = nz[0]
        y2 = nz[-1]

        ### Then work on the x distribution ###

        # Cut away y-side-bands and sum along Y
        img2 = image[y1:y2,:]
        imgX = image_processing.imageSumAlongY(img2)

        # Find centre-of-gravity and witdh
        (x0, sx) = image_processing.imageCentreOfMass(imgX)

        # Threshold level: 50%
        thr = imgX.max()/2.

        # Find FWHM
        nz = numpy.flatnonzero(imgX>thr)
        sx = float(nz[-1] - nz[0])

        return (x0, sx)
    
    def useAsCalibrationImage1(self):
        """Use current image as calibration image 1"""
        
        if self.currentPeak is None or self.currentFwhm is None:
            self.errorFound("No image available", "")
        
        self.set("xPeak1", self.currentPeak)
        self.set("xFWHM1", self.currentFwhm)
    
    def useAsCalibrationImage2(self):
        """Use current image as calibration image 2"""
        
        if self.currentPeak is None or self.currentFwhm is None:
            self.errorFound("No image available", "")
        
        self.set("xPeak2", self.currentPeak)
        self.set("xFWHM2", self.currentFwhm)

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
        
        try:
            calibrationFactor = self.get("calibrationFactor")
            shapeFactor = self.get("shapeFactor")
            
            imageArray = NDArray(image).getData()
            (x3, s3) = self.findPeakFWHM(imageArray)
            self.currentPeak = x3
            self.currentFwhm = s3
            w3 = s3 * shapeFactor * calibrationFactor
            
            h = Hash()
            
            h.set("xPeak3", x3)
            h.set("xFWHM3", s3)
            h.set("xWidth3", w3)
            
            # Set all properties at once
            self.set(h)
            
            self.log.DEBUG("Image processed!!!")

        except Exception as e:
            self.log.ERROR("In processImage: %s" % str(e))
    
if __name__ == "__main__":
    launchPythonDevice()
