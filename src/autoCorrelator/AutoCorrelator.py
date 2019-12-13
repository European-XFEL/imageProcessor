#!/usr/bin/env python

#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on May  9, 2014
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

import math
import numpy
import scipy.constants

from karabo.common.api import KARABO_SCHEMA_DISPLAY_TYPE_SCENES as DT_SCENES

from karabo.bound import (
    KARABO_CLASSINFO, DaqDataType, DOUBLE_ELEMENT, Hash, INPUT_CHANNEL,
    NODE_ELEMENT, MetricPrefix, OkErrorFsm, OUTPUT_CHANNEL,
    OVERWRITE_ELEMENT, PythonDevice, Schema, SLOT_ELEMENT, State,
    STRING_ELEMENT, Unit, UINT32_ELEMENT, VECTOR_DOUBLE_ELEMENT,
    VECTOR_STRING_ELEMENT
)

from image_processing import image_processing
from .overview import generate_scene

GAUSSIAN_FIT = "Gaussian Beam"
HYP_SEC_FIT = "Sech^2 Beam"


@KARABO_CLASSINFO("AutoCorrelator", "2.1")
class AutoCorrelator(PythonDevice, OkErrorFsm):

    # AKA shape-factor
    deconvolutionFactor = {GAUSSIAN_FIT: 1/math.sqrt(2),
                           HYP_SEC_FIT: 1/1.543}

    def __init__(self, configuration):
        # always call superclass constructor first!
        super(AutoCorrelator, self).__init__(configuration)

        self._ss.registerSlot(self.useAsCalibrationImage1)
        self._ss.registerSlot(self.useAsCalibrationImage2)
        self._ss.registerSlot(self.calibrate)
        self._ss.registerSlot(self.requestScene)

        self.currentPeak = None
        self.currentFwhm = None

        # boolean for schema_update
        self.is_schema_updated = False

    def __del__(self):
        super(AutoCorrelator, self).__del__()

    def requestScene(self, params):
        """Fulfill a scene request from another device.

        NOTE: Required by Scene Supply Protocol, which is defined in KEP 21.
               The format of the reply is also specified there.

        :param params: A `Hash` containing the method parameters
        """
        payload = Hash('success', False)

        name = params.get('name', default='')
        if name == 'scene':
            payload.set('success', True)
            payload.set('name', name)
            payload.set('data', generate_scene(self))
            self.reply(Hash('type', 'deviceScene', 'origin',
                            self.getInstanceId(),
                            'payload', payload))

    @staticmethod
    def expectedParameters(expected):

        data_in = Schema()
        data_out = Schema()
        (
            VECTOR_STRING_ELEMENT(expected).key('availableScenes')
                .setSpecialDisplayType(DT_SCENES)
                .readOnly().initialValue(['scene'])
                .commit(),

            INPUT_CHANNEL(expected).key("input")
                .displayedName("Input")
                .dataSchema(data_in)
                .commit(),

            # Images should be dropped if processor is too slow
            OVERWRITE_ELEMENT(expected).key("input.onSlowness")
                .setNewDefaultValue("drop")
                .commit(),

            DOUBLE_ELEMENT(expected)
                .key("xPeak1")
                .displayedName("Calibration: Image1 Peak x-Pos")
                .description("x-position of peak in first calibration image.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected)
                .key("xFWHM1")
                .displayedName("Calibration: Image1 Peak x-FWHM")
                .description("x-FWHM in first calibration image.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected)
                .key("xPeak2")
                .displayedName("Calibration: Image2 Peak x-Pos")
                .description("x-position of peak in second calibration image.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected)
                .key("xFWHM2")
                .displayedName("Calibration: Image2 Peak x-FWHM")
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
                .allowedStates(State.NORMAL)
                .commit(),

            DOUBLE_ELEMENT(expected)
                .key("delay")
                .displayedName("Delay ([fs] or [um])")
                .description("Delay between calibration images.")
                .assignmentOptional().defaultValue(0)
                .reconfigurable()
                .allowedStates(State.NORMAL)
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
                .description("Calculate calibration constant from two input "
                             "images.")
                .allowedStates(State.NORMAL)
                .commit(),

            DOUBLE_ELEMENT(expected)
                .key("calibrationFactor")
                .displayedName("Calibration constant [fs/px]")
                .description("The calibration constant.")
            #    .unit(Unit.???) # TODO Unit is fs/px
                .assignmentOptional().defaultValue(0)
                .reconfigurable()
                .commit(),

            STRING_ELEMENT(expected)
                .key("beamShape")
                .displayedName("Beam Shape")
                .description("Time shape of the beam.")
                .assignmentOptional().defaultValue("Gaussian Beam")
                .options(','.join([k for k in AutoCorrelator.
                                   deconvolutionFactor.keys()]), sep=",")
                .reconfigurable()
                .allowedStates(State.NORMAL)
                .commit(),

            UINT32_ELEMENT(expected)
                .key("xMinFit")
                .displayedName("Fit Lower Limit")
                .description("Lower limit for the fit.")
                .assignmentOptional().defaultValue(0)
                .unit(Unit.PIXEL)
                .reconfigurable()
                .commit(),

            UINT32_ELEMENT(expected)
                .key("xMaxFit")
                .displayedName("Fit Upper Limit")
                .description("Upper limit for the fit.")
                .assignmentOptional().defaultValue(10000)
                .unit(Unit.PIXEL)
                .reconfigurable()
                .commit(),

            UINT32_ELEMENT(expected)
                .key("fitStatus")
                .displayedName("Fit Status")
                .description("Error of fit procedure: .")
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected)
                .key("xPeak3")
                .displayedName("Input Image Peak x-Pos")
                .description("x-position of peak in the input image.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected)
                .key("xFWHM3")
                .displayedName("Input Image Peak x-FWHM")
                .description("x-FWHM in the input image.")
                .unit(Unit.PIXEL)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected)
                .key("pulseWidth")
                .displayedName("Pulse Duration")
                .description("Duration of the pulse.")
                .unit(Unit.SECOND).metricPrefix(MetricPrefix.FEMTO)
                .readOnly()
                .commit(),

            DOUBLE_ELEMENT(expected)
                .key("ePulseWidth")
                .displayedName("Pulse Duration Error")
                .description("Uncertainty of the pulse duration arising "
                             "from fit procedure.")
                .unit(Unit.SECOND).metricPrefix(MetricPrefix.FEMTO)
                .readOnly()
                .commit(),

            NODE_ELEMENT(data_out).key("data")
                .displayedName("Data")
                .setDaqDataType(DaqDataType.TRAIN)
                .commit(),

            VECTOR_DOUBLE_ELEMENT(data_out)
                .key("data.profileX")
                .displayedName("Image X Profile")
                .description("Profile along x-axis of second harmonic beam.")
                .readOnly()
                .commit(),

            VECTOR_DOUBLE_ELEMENT(data_out)
                .key("data.profileXFit")
                .displayedName("X Profile Fit")
                .description("Fit Profile along x-axis of second "
                             "harmonic beam.")
                .readOnly()
                .commit(),

            OUTPUT_CHANNEL(expected)
                .key("output")
                .displayedName("Output")
                .dataSchema(data_out)
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
        beamShape = self.get("beamShape")

        if inputConfig.has("calibrationFactor"):
            # Calibration factor has changed
            calibrationFactor = inputConfig.get("calibrationFactor")
            recalculateWidth = True

        if inputConfig.has("beamShape"):
            # Shape factor has changed
            beamShape = inputConfig.get("beamShape")
            recalculateWidth = True

        if recalculateWidth is True and self.currentFwhm is not None:
            sF = self.deconvolutionFactor[beamShape]
            w3 = self.currentFwhm * sF * calibrationFactor
            ew3 = self.currentEFwhm * sF * calibrationFactor
            self.set("pulseWidth", w3)
            self.set("ePulseWidth", ew3)
            self.log.DEBUG("Image re-processed!!!")

    def calibrate(self):
        '''Calculate calibration constant'''

        self.log.INFO("Calibrating auto-correlator...")

        try:
            delayUnit = self["delayUnit"]
            if delayUnit == "fs":
                delay = self["delay"]
            elif delayUnit == "um":
                # Must convert to time
                # * 2 due to double pass through adjustable length
                delay = 2 * 1e+9 * self["delay"] / scipy.constants.c
            else:
                self.errorFound("Unknown delay unit #s" % delayUnit, "")

            dX = self["xPeak1"] - self["xPeak2"]
            if dX == 0:
                self.errorFound("Same peak position for the two images", "")

            calibrationFactor = abs(delay / dX)
            self.set("calibrationFactor", calibrationFactor)

        except:
            self.errorFound("Cannot calculate calibration constant", "")

    def findPeakFWHM(self, image, threshold=0.5):
        '''Find x-position of peak in 2-d image, and FWHM along x direction'''
        if not isinstance(image, numpy.ndarray) or image.ndim != 2:
            return None

        # First work on y distribution #

        # sum along X
        imgY = image_processing.imageSumAlongX(image)

        # Threshold level
        thr = threshold * imgY.max()

        # Find 1st and last point above threshold
        nz = numpy.flatnonzero(imgY > thr)
        y1 = nz[0]
        y2 = nz[-1]

        # Then work on the x distribution #

        # Cut away y-side-bands and sum along Y
        img2 = image[y1:y2, :]
        imgX = image_processing.imageSumAlongY(img2)

        # perform the fit
        beamShape = self["beamShape"]
        x_min_fit = self["xMinFit"]
        x_max_fit = self["xMaxFit"]
        if x_max_fit > len(imgX):
            x_max_fit = len(imgX) - 1
            self.set("xMaxFit", x_max_fit)

        if beamShape == GAUSSIAN_FIT:
            pars, cov, err = \
                image_processing.fitGauss(imgX[x_min_fit:x_max_fit])
            x0 = pars[1] + x_min_fit
            # height = par[0], x0 = pars[1], sx = pars[2]
            fit_func = image_processing.gauss1d(
                numpy.linspace(0, len(imgX) - 1, len(imgX)),
                pars[0],  x0,  pars[2])
        elif beamShape == HYP_SEC_FIT:
            pars, cov, err = \
                image_processing.fitSech2(imgX[x_min_fit:x_max_fit])
            x0 = pars[1] + x_min_fit
            fit_func = image_processing.sqsech1d(
                numpy.linspace(0, len(imgX) - 1, len(imgX)),
                pars[0], x0, pars[2])
        else:
            msg = f"Error: Unknown beam shape {beamShape} provided"
            self.log.ERROR(msg)
            raise ValueError(msg)
        self.set("fitStatus", err)

        # Threshold level
        thr = threshold * fit_func.max()
        # Find 1st and last point above threshold
        nz = numpy.flatnonzero(imgY > thr)
        # Find FWHM of fit values
        sx = float(nz[-1] - nz[0])
        # Find error of FWHM
        esx = sx / pars[2] * cov[1, 1]

        # fill output channel
        output_data = Hash('data.profileX', imgX.tolist(),
                           'data.profileXFit', fit_func.tolist())
        self.writeChannel('output', output_data)

        # return the fit mean, sigma, and the error on the mean
        return (x0, sx, esx)

    def useAsCalibrationImage1(self):
        '''Use current image as calibration image 1'''

        if self.currentPeak is None or self.currentFwhm is None:
            self.errorFound("No image available", "")

        self.set("xPeak1", self.currentPeak)
        self.set("xFWHM1", self.currentFwhm)

    def useAsCalibrationImage2(self):
        '''Use current image as calibration image 2'''

        if self.currentPeak is None or self.currentFwhm is None:
            self.errorFound("No image available", "")

        self.set("xPeak2", self.currentPeak)
        self.set("xFWHM2", self.currentFwhm)

    def onData(self, data, metaData):

        try:
            if not self.is_schema_updated:
                self.update_output_schema(data)
                self.is_schema_updated = True

            if data.has('data.image'):
                self.processImage(data['data.image'])
            elif data.has('image'):
                # To ensure backward compatibility
                # with older versions of cameras
                self.processImage(data['image'])
            else:
                self.log.WARN("data does not have any image")
        except Exception as e:
            self.log.ERROR("Exception caught in onData: %s" % str(e))

    def onEndOfStream(self, inputChannel):
        connected_devices = inputChannel.getConnectedOutputChannels().keys()
        dev = [*connected_devices][0]
        self.log.INFO(f"onEndOfStream called: Channel {dev} "
                      "stopped streaming.")

        # schema should updated at next connection
        self.is_schema_updated = False

    def processImage(self, imageData):

        try:
            calibrationFactor = self.get("calibrationFactor")
            sF = self.deconvolutionFactor[self.get("beamShape")]

            imageArray = imageData.getData()
            (x3, s3, es3) = self.findPeakFWHM(imageArray)
            self.currentPeak = x3
            self.currentFwhm = s3
            self.currentEFwhm = es3
            w3 = s3 * sF * calibrationFactor
            ew3 = es3 * sF * calibrationFactor

            h = Hash()

            h.set("xPeak3", x3)
            h.set("xFWHM3", s3)
            h.set("pulseWidth", w3)
            h.set("ePulseWidth", ew3)

            # Set all properties at once
            self.set(h)

            msg = "Image processing Ok"
            if self["status"] != msg:
                self.log.DEBUG(msg)
                self.set("status", msg)

        except Exception as e:
            msg = f"In processImage: {e}"
            if self["status"] != f"ERROR: {msg}":
                self.log.ERROR(msg)
                self.set("status", f"ERROR: {msg}")
            h = Hash()
            h.set("pulseWidth", 0)
            h.set("ePulseWidth", 0)
            h.set("fitStatus", 0)
            self.set(h)

    def update_output_schema(self, data):
        # Get device configuration before schema update
        if data.has('data.image'):
            image = data['data.image']
        elif data.has('image'):
            image = data['image']
        shape = image.getDimensions()
        width = shape[0]

        newSchema = Schema()
        dataSchema = Schema()
        (
            NODE_ELEMENT(dataSchema).key("data")
            .displayedName("Data")
            .setDaqDataType(DaqDataType.TRAIN)
            .commit(),

            VECTOR_DOUBLE_ELEMENT(dataSchema)
            .key("data.profileX")
            .displayedName("Image X Profile")
            .description("Profile along x-axis of second harmonic beam.")
            .readOnly()
            .commit(),

            VECTOR_DOUBLE_ELEMENT(dataSchema)
            .key("data.profileXFit")
            .displayedName("X Profile Fit")
            .description("Fit Profile along x-axis of second "
                         "harmonic beam.")
            .readOnly()
            .commit(),

            dataSchema.setMaxSize("data.profileX", width),
            dataSchema.setMaxSize("data.profileXFit", width),

            OUTPUT_CHANNEL(newSchema).key("output")
            .displayedName("Output")
            .dataSchema(dataSchema)
            .commit(),
        )

        self.updateSchema(newSchema)
