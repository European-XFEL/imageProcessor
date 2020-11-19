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
    BOOL_ELEMENT, DaqDataType, DOUBLE_ELEMENT, Hash, INPUT_CHANNEL,
    KARABO_CLASSINFO, MetricPrefix, NODE_ELEMENT, OUTPUT_CHANNEL,
    OVERWRITE_ELEMENT, PythonDevice, Schema, SLOT_ELEMENT, State,
    STRING_ELEMENT, UINT32_ELEMENT, Unit, VECTOR_DOUBLE_ELEMENT,
    VECTOR_STRING_ELEMENT
)

from image_processing import image_processing
from .overview import generate_scene
from ._version import version

GAUSSIAN_FIT = "Gaussian Beam"
HYP_SEC_FIT = "Sech^2 Beam"


@KARABO_CLASSINFO("AutoCorrelator", version)
class AutoCorrelator(PythonDevice):

    # AKA shape-factor
    deconvolution_factor = {GAUSSIAN_FIT: 1 / math.sqrt(2),
                            HYP_SEC_FIT: 1 / 1.543}

    @staticmethod
    def expectedParameters(expected):

        data_in = Schema()
        data_out = Schema()
        (
            OVERWRITE_ELEMENT(expected).key("state")
            .setNewOptions(State.ON, State.PROCESSING, State.ERROR)
            .setNewDefaultValue(State.ON)
            .commit(),

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
            .commit(),

            DOUBLE_ELEMENT(expected)
            .key("delay")
            .displayedName("Delay ([fs] or [um])")
            .description("Delay between calibration images.")
            .assignmentOptional().defaultValue(0)
            .reconfigurable()
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
            .commit(),

            SLOT_ELEMENT(expected).key("reset")
            .displayedName("Reset Error")
            .description("Acknowledge error.")
            .commit(),

            DOUBLE_ELEMENT(expected)
            .key("calibrationFactor")
            .displayedName("Calibration constant [fs/px]")
            .description("The calibration constant.")
            # .unit(Unit.???) # TODO Unit is fs/px
            .assignmentOptional().defaultValue(0)
            .reconfigurable()
            .commit(),

            STRING_ELEMENT(expected)
            .key("beamShape")
            .displayedName("Beam Shape")
            .description("Time shape of the beam.")
            .assignmentOptional().defaultValue("Gaussian Beam")
            .options(','.join([k for k in AutoCorrelator.
                              deconvolution_factor.keys()]), sep=",")
            .reconfigurable()
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
            .description("Error of fit procedure: 1-3 means good fit. "
                         "See device documentation for further details.")
            .readOnly()
            .commit(),

            BOOL_ELEMENT(expected).key("subtractPedestal")
            .displayedName("Subtract Pedestal")
            .description("Subtract the pedestal, calculated from linear "
                         "interpolation between first and last point.")
            .assignmentOptional().defaultValue(False)
            .reconfigurable()
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
            .key("data.integralX")
            .displayedName("Image X Integral")
            .description("Integral along x-axis of second harmonic beam.")
            .readOnly()
            .commit(),

            VECTOR_DOUBLE_ELEMENT(data_out)
            .key("data.integralXFit")
            .displayedName("X Integral Fit")
            .description("Fit integral along x-axis of second "
                         "harmonic beam.")
            .readOnly()
            .commit(),

            OUTPUT_CHANNEL(expected)
            .key("output")
            .displayedName("Output")
            .dataSchema(data_out)
            .commit(),
        )

    def __init__(self, configuration):
        # always call superclass constructor first!
        super(AutoCorrelator, self).__init__(configuration)

        self.current_peak = None
        self.current_fwhm = None
        self.current_e_fwhm = None

        # boolean for schema_update
        self.is_schema_updated = False

        # Register slots
        self.KARABO_SLOT(self.useAsCalibrationImage1)
        self.KARABO_SLOT(self.useAsCalibrationImage2)
        self.KARABO_SLOT(self.calibrate)
        self.KARABO_SLOT(self.reset)
        self.KARABO_SLOT(self.requestScene)

        # Register call-backs
        self.KARABO_ON_DATA("input", self.onData)
        self.KARABO_ON_EOS("input", self.onEndOfStream)

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

    def preReconfigure(self, input_config):
        self.log.INFO("preReconfigure")

        recalculate_width = False
        calibration_factor = self.get("calibrationFactor")
        beam_shape = self.get("beamShape")

        if input_config.has("calibrationFactor"):
            # Calibration factor has changed
            calibration_factor = input_config.get("calibrationFactor")
            recalculate_width = True

        if input_config.has("beamShape"):
            # Shape factor has changed
            beam_shape = input_config.get("beamShape")
            recalculate_width = True

        if recalculate_width is True and self.current_fwhm is not None:
            s_f = self.deconvolution_factor[beam_shape]
            w3 = self.current_fwhm * s_f * calibration_factor
            ew3 = self.current_e_fwhm * s_f * calibration_factor
            h = Hash("pulseWidth", w3, "ePulseWidth", ew3)
            self.set(h)
            self.log.DEBUG("Image re-processed!!!")

    def calibrate(self):
        """Calculate calibration constant"""

        self.log.INFO("Calibrating auto-correlator...")

        delay_unit = self["delayUnit"]
        if delay_unit == "fs":
            delay = self["delay"]
        elif delay_unit == "um":
            # Must convert to time
            # * 2 due to double pass through adjustable length
            delay = 2 * 1e+9 * self["delay"] / scipy.constants.c
        else:
            raise RuntimeError("Unknown delay unit #s" % delay_unit)

        d_x = self["xPeak1"] - self["xPeak2"]
        if d_x == 0:
            raise RuntimeError("Same peak position for the two images")

        calibration_factor = abs(delay / d_x)
        self.set("calibrationFactor", calibration_factor)

    def find_peak_fwhm(self, image, threshold=0.5):
        """Find x-position of peak in 2-d image, and FWHM along x direction"""
        if not isinstance(image, numpy.ndarray) or image.ndim != 2:
            return None

        # First work on y distribution #

        # sum along X
        img_y = image_processing.imageSumAlongX(image)

        # Threshold level
        thr = threshold * img_y.max()

        # Find 1st and last point above threshold
        nz = numpy.flatnonzero(img_y > thr)
        y1 = nz[0]
        y2 = nz[-1]

        # Then work on the x distribution #

        # Cut away y-side-bands and sum along Y
        img2 = image[y1:y2, :]
        img_x = image_processing.imageSumAlongY(img2)

        # perform the fit
        beam_shape = self["beamShape"]
        x_min_fit = self["xMinFit"]
        x_max_fit = self["xMaxFit"]
        if x_max_fit > len(img_x):
            x_max_fit = len(img_x) - 1
            self.set("xMaxFit", x_max_fit)

        if x_max_fit - x_min_fit < 4:
            msg = f"Fit window too narrow: [{x_min_fit}, {x_max_fit}]"
            raise ValueError(msg)

        x_axis = numpy.linspace(0, len(img_x) - 1, len(img_x))
        # get pedestal if required
        if self["subtractPedestal"]:
            alpha = (img_x[-1] - img_x[0]) / (x_axis[-1] - x_axis[0])
            ped_func = alpha * x_axis + img_x[0]
            img_x = numpy.subtract(img_x, ped_func)

        if beam_shape == GAUSSIAN_FIT:
            pars, cov, err = \
                image_processing.fitGauss(img_x[x_min_fit:x_max_fit])
            x0 = pars[1] + x_min_fit
            # height = par[0], x0 = pars[1], sx = pars[2]
            fit_func = image_processing.gauss1d(x_axis, pars[0],  x0,  pars[2])
        elif beam_shape == HYP_SEC_FIT:
            pars, cov, err = \
                image_processing.fitSech2(img_x[x_min_fit:x_max_fit])
            x0 = pars[1] + x_min_fit
            fit_func = image_processing.sqsech1d(x_axis, pars[0], x0, pars[2])
        else:
            msg = f"Error: Unknown beam shape {beam_shape} provided"
            self.log.ERROR(msg)
            raise ValueError(msg)

        # Threshold level
        thr = threshold * fit_func.max()
        # Find 1st and last point above threshold
        nz = numpy.flatnonzero(fit_func > thr)
        # Find FWHM of fit values
        sx = float(nz[-1] - nz[0])
        # Find error of FWHM
        esx = sx / pars[2] * cov[1, 1]

        # fill output channel
        output_data = Hash('data.integralX', img_x.tolist(),
                           'data.integralXFit', fit_func.tolist())
        self.writeChannel('output', output_data)

        # return the fit mean, sigma, and the error on the mean
        return x0, sx, esx, err

    def useAsCalibrationImage1(self):
        """Use current image as calibration image 1"""

        if self.current_peak is None or self.current_fwhm is None:
            self.log.ERROR("No image available")
            self.updateState(State.ERROR)
            return

        h = Hash("xPeak1", self.current_peak, "xFWHM1", self.current_fwhm)
        self.set(h)

    def useAsCalibrationImage2(self):
        """Use current image as calibration image 2"""

        if self.current_peak is None or self.current_fwhm is None:
            self.log.ERROR("No image available")
            self.updateState(State.ERROR)
            return

        h = Hash("xPeak2", self.current_peak, "xFWHM2", self.current_fwhm)
        self.set(h)

    def reset(self):
        if self['state'] == State.ERROR:
            self.updateState(State.ON)

    def onData(self, data, metaData):

        if self['state'] != State.PROCESSING:
            self.updateState(State.PROCESSING)

        try:
            if not self.is_schema_updated:
                self.update_output_schema(data)
                self.is_schema_updated = True

            if data.has('data.image'):
                self.process_image(data['data.image'])
            elif data.has('image'):
                # To ensure backward compatibility
                # with older versions of cameras
                self.process_image(data['image'])
            else:
                self.log.WARN("data does not have any image")
        except Exception as e:
            self.log.ERROR("Exception caught in onData: %s" % str(e))

    def onEndOfStream(self, inputChannel):
        connected_devices = inputChannel.getConnectedOutputChannels().keys()
        dev = [*connected_devices][0]
        self.log.INFO(f"onEndOfStream called: Channel {dev} "
                      "stopped streaming.")

        # schema should be updated at next connection
        self.is_schema_updated = False

        if self['state'] == State.PROCESSING:
            self.updateState(State.ON)

    def process_image(self, imageData):

        try:
            calibration_factor = self.get("calibrationFactor")
            s_f = self.deconvolution_factor[self.get("beamShape")]

            image_array = imageData.getData()
            x3, s3, es3, fit_status = self.find_peak_fwhm(image_array)
            self.current_peak = x3
            self.current_fwhm = s3
            self.current_e_fwhm = es3
            w3 = s3 * s_f * calibration_factor
            ew3 = es3 * s_f * calibration_factor

            h = Hash()
            h.set("fitStatus", fit_status)

            # save in case fit status < 4
            # from 4 on no improvement was measured
            if 0 < fit_status < 4:
                h.set("xPeak3", x3)
                h.set("xFWHM3", s3)
                h.set("pulseWidth", w3)
                h.set("ePulseWidth", ew3)

                msg = "Image processing Ok"
                if self["status"] != msg:
                    self.log.DEBUG(msg)
                    h.set("status", msg)
            else:
                msg = f"Warning: Fit status is {fit_status}"
                self.log.DEBUG(msg)

            # Set all properties at once
            self.set(h)

        except Exception as e:
            msg = f"In processImage: {e}"
            if self["status"] != f"ERROR: {msg}":
                self.log.ERROR(msg)
                self.set("status", f"ERROR: {msg}")

    def update_output_schema(self, data):
        if data.has('data.image'):
            image = data['data.image']
        elif data.has('image'):
            image = data['image']
        shape = image.getDimensions()
        width = shape[1]

        new_schema = Schema()
        data_schema = Schema()
        (
            NODE_ELEMENT(data_schema).key("data")
            .displayedName("Data")
            .setDaqDataType(DaqDataType.TRAIN)
            .commit(),

            VECTOR_DOUBLE_ELEMENT(data_schema)
            .key("data.integralX")
            .displayedName("Image X Integral")
            .description("Integral along x-axis of second harmonic beam.")
            .maxSize(width)
            .readOnly()
            .commit(),

            VECTOR_DOUBLE_ELEMENT(data_schema)
            .key("data.integralXFit")
            .displayedName("X Integral Fit")
            .description("Fit integral along x-axis of second "
                         "harmonic beam.")
            .maxSize(width)
            .readOnly()
            .commit(),

            OUTPUT_CHANNEL(new_schema).key("output")
            .displayedName("Output")
            .dataSchema(data_schema)
            .commit(),
        )

        self.updateSchema(new_schema)
