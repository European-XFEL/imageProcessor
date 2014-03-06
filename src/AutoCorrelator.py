#!/usr/bin/env python

__author__="andrea.parenti@xfel.eu"
__date__ ="February, 2014, 02:13 PM"
__copyright__="Copyright (c) 2010-2013 European XFEL GmbH Hamburg. All rights reserved."

import sys
import threading
import time

import numpy
import scipy
import scipy.constants

from karabo.device import *
from karabo.ok_error_fsm import OkErrorFsm
from karabo.fsm import *

import image_processing


@KARABO_CLASSINFO("AutoCorrelator", "1.0")
class AutoCorrelator(PythonDevice, OkErrorFsm):

    def __init__(self, configuration):
        # always call PythonDevice constructor first!
        super(AutoCorrelator,self).__init__(configuration)
        
        #**************************************************************
        #*                        Events                              *
        #**************************************************************
        KARABO_FSM_EVENT0(self, 'CalibrateEvent', 'calibrate')
        
        #**************************************************************
        #*                    Transition Actions                      *
        #**************************************************************
        KARABO_FSM_ACTION0('CalibrateAction', self.calibrateAction)
        
        #**************************************************************
        #*                 Top Machine (redefinition)                 *
        #**************************************************************

        #  Source-State    Event     Target-State  Action          Guard
        stateMachineTransitionTable = [
            ('Ok',    'ErrorFoundEvent', 'Error', 'ErrorFoundAction', 'none'),
            ('Ok',    'CalibrateEvent',  'Ok',    'CalibrateAction',  'none'),
            ('Error', 'ResetEvent',      'Ok',    'none',             'none')
        ]

        #                           Name                Transition-Table  Initial-State
        KARABO_FSM_STATE_MACHINE('StateMachine', stateMachineTransitionTable, 'Ok')
        self.fsm = KARABO_FSM_CREATE_MACHINE('StateMachine')

        self._ss.registerSlot(self.calibrate)
    
    @staticmethod
    def expectedParameters(expected):
        '''Description of device parameters statically known'''
        (
        SLOT_ELEMENT(expected).key("calibrate")
                .displayedName("Calibrate")
                .description("Calculata calibration constant from two input images.")
                .allowedStates("Ok")
                .commit(),
        
        PATH_ELEMENT(expected)
                .key("inputImage1")
                .displayedName("Calibration Image 1")
                .description("First image used for calibration.")
                .assignmentOptional().defaultValue("")
                .reconfigurable()
                .allowedStates("Ok")
                .commit()
                ,
        
        IMAGE_ELEMENT(expected)
                .key("image1")
                .displayedName("Calibration Image 1")
                .description("Display first image used for calibration.")
                .commit()
                ,
        
        DOUBLE_ELEMENT(expected)
                .key("xPeak1")
                .displayedName("Image1 xPeak")
                .description("x-position of peak in first calibration image.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit()
                ,
        
        DOUBLE_ELEMENT(expected)
                .key("xFWHM1")
                .displayedName("Image1 xFWHM")
                .description("x-FWHM in first calibration image.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit()
                ,
        
        PATH_ELEMENT(expected)
                .key("inputImage2")
                .displayedName("Calibration Image 2")
                .description("Second image used for calibration.")
                .assignmentOptional().defaultValue("")
                .reconfigurable()
                .allowedStates("Ok")
                .commit()
                ,
        
        IMAGE_ELEMENT(expected)
                .key("image2")
                .displayedName("Calibration Image 2")
                .description("Display second image used for calibration.")
                .commit()
                ,
        
        DOUBLE_ELEMENT(expected)
                .key("xPeak2")
                .displayedName("Image2 xPeak")
                .description("x-position of peak in second calibration image.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit()
                ,
        
        DOUBLE_ELEMENT(expected)
                .key("xFWHM2")
                .displayedName("Image2 xFWHM")
                .description("x-FWHM in second calibration image.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit()
                ,
        
        STRING_ELEMENT(expected)
                .key("delayUnit")
                .displayedName("Delay Unit")
                .description("Unit of the delay between calibration images.")
                .assignmentOptional().defaultValue("fs")
                .options("fs um")
                .reconfigurable()
                .allowedStates("Ok")
                .commit()
                ,
        
        DOUBLE_ELEMENT(expected)
                .key("delay")
                .displayedName("Delay")
                .description("Delay between calibration images.")
                .assignmentOptional().defaultValue(0)
                .reconfigurable()
                .allowedStates("Ok")
                .commit()
                ,
        
        DOUBLE_ELEMENT(expected)
                .key("calibration")
                .displayedName("Calibration constant [fs/px]")
                .description("The calibration constant.")
                # .unit(Unit.???) # TODO Unit is fs/px
                .assignmentOptional().defaultValue(0)
                .reconfigurable()
                .allowedStates("Ok")
                .commit()
                ,
                
        # TODO set with input channel
        PATH_ELEMENT(expected)
                .key("inputImage3")
                .displayedName("Input Image")
                .description("Input image, for which peak width is evaluated.")
                .assignmentOptional().defaultValue("")
                .reconfigurable()
                .allowedStates("Ok")
                .commit()
                ,
        
        IMAGE_ELEMENT(expected)
                .key("image3")
                .displayedName("Input Image 3")
                .description("Input image, for which peak width is evaluated.")
                .commit()
                ,
        
        DOUBLE_ELEMENT(expected)
                .key("shapeFactor")
                .displayedName("Shape Factor")
                .description("Shape factor to convert FWHM to peak width.")
                .assignmentOptional().defaultValue(1.)
                # .options("1.") # TODO...
                .reconfigurable()
                .allowedStates("Ok")
                .commit()
                ,
        
        DOUBLE_ELEMENT(expected)
                .key("xPeak3")
                .displayedName("Image3 xPeak")
                .description("x-position of peak in the input image.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit()
                ,
        
        DOUBLE_ELEMENT(expected)
                .key("xFWHM3")
                .displayedName("Image3 xFWHM")
                .description("x-FWHM in the input image.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit()
                ,
        
        DOUBLE_ELEMENT(expected)
                .key("xWidth3")
                .displayedName("Image3 Peak Width")
                .description("x-Width of the input image.")
                .unit(Unit.SECOND).metricPrefix(MetricPrefix.FEMTO)
                .readOnly()
                .commit()
                ,

        )

    ##############################################
    #   Implementation of State Machine methods  #
    ##############################################
    
    def calibrateAction(self):
        '''Calculate calibration constant'''
        
        self.log.INFO("Calibrating auto-correlator...")
        
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
            
        calibration = abs(delay / dX)
        self.set("calibration", calibration)
    
    def preReconfigure(self, inputConfig):
        self.log.INFO("preReconfigure")
        
        if inputConfig.has("inputImage1"):
            image1 = None
            filename1 = inputConfig["inputImage1"]
            self.log.INFO("Loading calibration image %s..." % filename1)
            try:
                image1 = numpy.load(filename1)
                dimX = image1.shape[1]
                dimY = image1.shape[0]
                rawImage1 = RawImageData(image1.reshape(dimX, dimY), EncodingType.GRAY)
                self.set("image1", rawImage1)
                
            except:
                self.errorFound("Cannot load image %s" % filename1, "")
            
            try:
                (x1, s1) = self.findPeakFWHM(image1)
                self.set("xPeak1", x1)
                self.set("xFWHM1", s1)
            
            except:
                self.errorFound("Cannot process image %s" % filename1, "")
            
        if inputConfig.has("inputImage2"):
            image2 = None
            filename2 = inputConfig["inputImage2"]
            self.log.INFO("Loading calibration image %s..." % filename2)
            try:
                image2 = numpy.load(filename2)
                dimX = image2.shape[1]
                dimY = image2.shape[0]
                rawImage2 = RawImageData(image2.reshape(dimX, dimY), EncodingType.GRAY)
                self.set("image2", rawImage2)
                
            except:
                self.errorFound("Cannot load image %s" % filename2, "")
                
            try:
                (x2, s2) = self.findPeakFWHM(image2)
                self.set("xPeak2", x2)
                self.set("xFWHM2", s2)
            
            except:
                self.errorFound("Cannot process image %s" % filename2, "")
        
        if inputConfig.has("inputImage3"):
            image3 = None
            filename3 = inputConfig["inputImage3"]
            self.log.INFO("Loading calibration image %s..." % filename3)
            try:
                image3 = numpy.load(filename3)
                dimX = image3.shape[1]
                dimY = image3.shape[0]
                rawImage3 = RawImageData(image3.reshape(dimX, dimY), EncodingType.GRAY)
                self.set("image3", rawImage3)
                
            except:
                self.errorFound("Cannot load image %s" % filename3, "")
                
            try:
                (x3, s3) = self.findPeakFWHM(image3)
                self.set("xPeak3", x3)
                self.set("xFWHM3", s3)
            
            except:
                self.errorFound("Cannot process image %s" % filename3, "")
    
    def postReconfigure(self):
        self.log.INFO("postReconfigure")
        
        s3 = self.get("xFWHM3")
        calibration = self.get("calibration")
        shapeFactor = self.get("shapeFactor")
        w3 = s3 * shapeFactor * calibration
        
        self.set("xWidth3", w3)
        
    def findPeakFWHM(self, image, threshold=0.5):
        """Find x-position of peak in 2-d image, and FWHM along x direction"""
        if type(image)!=numpy.ndarray or image.ndim!=2:
            return None

        ### First work on y-projection ###

        # y-projection
        imgY = image_processing.imageYProjection(image)

        # Threshold level
        thr = threshold*imgY.max()

        # Find 1st and last point above threshold
        nz = numpy.flatnonzero(imgY>thr)
        y1 = nz[0]
        y2 = nz[-1]

        ### Then work on the x-projection ###

        # Cut away y-side-bands and project image onto x axis
        img2 = image[y1:y2,:]
        imgX = image_processing.imageXProjection(img2)

        # Find centre-of-gravity and witdh
        (x0, sx) = image_processing.imageCentreOfMass(imgX)

        # Threshold level: 50%
        thr = imgX.max()/2.

        # Find FWHM
        nz = numpy.flatnonzero(imgX>thr)
        sx = float(nz[-1] - nz[0])

        return (x0, sx)


    # Put here more state machibe actioins if needed... . See FSM API
   
# This entry used by device server
if __name__ == "__main__":
    launchPythonDevice()
