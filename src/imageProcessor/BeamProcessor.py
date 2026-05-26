#############################################################################
# Author: carinanc
# Created on May 26, 2021, 03:08 PM
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################
import numpy as np

from karabo.middlelayer import (
    AccessMode, Assignment, Bool, Device, Hash, ImageData, InputChannel,
    KaraboValue, Node, OutputChannel, Overwrite, State, String, VectorString,
    background, get_image_data, get_timestamp, slot, unit)
from karabo.native import wrap

from ._version import version as deviceVersion
from .algorithms import (
    Beam, Ellipse, butterworth_filter, elongate, fit_gaussian, gaussian,
    get_origin, to_degrees)
from .const import Origin
from .nodes import ChannelNode, GaussianNode, ParametersNode, PropertiesNode
from .scenes_beamprocessor import get_scene


def create_value(value, timestamp=None, units=None):
    if isinstance(value, KaraboValue):
        value = value.value
    value = wrap(value)
    if timestamp is not None:
        value.timestamp = timestamp
    if units is not None:
        value = value * units
    return value


# -----------------------------------------------------------------------------
# Device class

class BeamProcessor(Device):
    __version__ = deviceVersion

    state = Overwrite(
        defaultValue=State.ON,
        options=[State.ON, State.PROCESSING])

    interfaces = VectorString(
        defaultValue=["Processor"],
        accessMode=AccessMode.READONLY)

    availableScenes = VectorString(
        displayedName="Available Scenes",
        displayType="Scenes",
        accessMode=AccessMode.READONLY,
        defaultValue=["overview"],)

    def _calc_imhomogeneous_background(self, image):
        samples = self.parameters.inhomogeneousBackgroundSamples.value
        n_y, n_x = image.shape
        if not samples or samples > n_y:
            raw = filtered = np.zeros(n_x)
        else:
            raw = np.vstack((image[:samples], image[-samples:])).mean(axis=0)
            filtered = butterworth_filter(raw, cutoff=15)

        hash_list = [
            Hash("label", "raw",
                 "x", np.arange(raw.size).tolist(),
                 "y", raw.tolist(),
                 "plotType", "scatter"),
            Hash("label", "filtered",
                 "x", np.arange(filtered.size).tolist(),
                 "y", filtered.tolist(),
                 "plotType", "line"),
        ]
        self.output.schema.data.inhomogeneousBackground = hash_list

        return filtered

    def _set_properties(self, beam, timestamp=None):
        # Set the metrics to the device
        params = self.parameters
        width_scale = params.transform.beamWidthScale.value
        pixel_scale = params.transform.pixelScale.value
        pixel_translate = params.transform.pixelTranslate.value

        scaled_width = np.multiply(beam.widths, width_scale)

        # Transform beam properties according to scale and translate
        centroid = np.add(beam.centroid, pixel_translate) * pixel_scale
        widths = np.multiply(beam.widths, pixel_scale)

        # Uncertainty on x0, y0 estimation.
        uncertainties = np.multiply(beam.uncertainties, pixel_scale)

        # Get max value and position
        max_value, max_pos = beam.maximum()
        max_pos = np.add(max_pos, pixel_translate) * pixel_scale

        props = {
            'energy': create_value(beam.energy / params.energyScale,
                                   timestamp),

            'x0': create_value(centroid[0], timestamp),
            'y0': create_value(centroid[1], timestamp),

            'a': create_value(widths[0], timestamp),
            'b': create_value(widths[1], timestamp),
            'majorAxisScaled': create_value(scaled_width[0], timestamp),
            'minorAxisScaled': create_value(scaled_width[1], timestamp),

            'theta': create_value(to_degrees(beam.angle, reflected=True),
                                  timestamp, units=unit.degrees),

            'peakX': create_value(max_pos[0], timestamp),
            'peakY': create_value(max_pos[1], timestamp),
            'peak': create_value(max_value, timestamp),

            'ex01d': create_value(uncertainties[0], timestamp),
            'ey01d': create_value(uncertainties[1], timestamp)
        }

        self._set_beam(props)

    def _set_beam(self, props):
        nodes = (self.beamProperties, self.output.schema.data.beamProperties)
        for node in nodes:
            for prop, value in props.items():
                setattr(node, prop, value)

    def _set_transform(self, *, translate, scale=None):
        output_transform = self.output.schema.data.transform
        params_transform = self.parameters.transform

        if scale is None:
            scale = params_transform.pixelScale
        else:
            scale = list(scale)
            params_transform.pixelScale = scale
        output_transform.pixelScale = scale

        params_transform.set_translate(*translate)
        output_transform.pixelTranslate = list(translate)

    def _set_axis(self, data, *, name: str, translate=0):
        pixel_scale = self.parameters.transform.pixelScale.value
        width_scale = self.parameters.transform.beamWidthScale.value
        super_gaussian = self.parameters.isSuperGaussian

        x_fit, y_fit = np.array([]), np.array([])
        pos, width, r2, uncertainty = np.nan, np.nan, np.nan, np.nan

        x_raw, y_raw = data
        if len(x_raw) and len(y_raw):
            # Translate the x-axis to a specified origin
            x_raw = (x_raw + translate) * pixel_scale

            # Fit gaussian to data
            pos, width, p0, r2, uncertainty = (
                fit_gaussian(x_raw, y_raw, super_gaussian=super_gaussian))

            if p0 is not None:
                x_fit = elongate(x_raw)
                y_fit = gaussian(x_fit, *p0)

        node = getattr(self, name)
        node.pos = pos
        node.width = width * width_scale
        node.r2 = r2
        node.uncertainty = uncertainty

        hash_list = [
            Hash("label", "beam",
                 "x", x_raw.tolist(),
                 "y", y_raw.tolist(),
                 "plotType", "scatter"),
            Hash("label", "fit",
                 "x", x_fit.tolist(),
                 "y", y_fit.tolist(),
                 "plotType", "line"),
        ]
        setattr(self.output.schema.data, name, hash_list)

    # Input Channel Settings

    @InputChannel(displayedName="Input", raw=True)
    async def input(self, data, meta):
        # Update device state
        if self.state != State.PROCESSING:
            self.state = State.PROCESSING
        timestamp = get_timestamp(meta.timestamp.timestamp)
        self.lastUpdated = str(timestamp)

        # Get input data
        raw_image = get_image_data(data)
        # roi = params.roi.value if params.has_roi else None

        # Subtract inhomogeneous background
        raw_image = raw_image - self._calc_imhomogeneous_background(raw_image)

        # Detect the beam
        beam = await background(self.detect_beam, raw_image)

        # Gracefully exit if beam is not detected
        # First check: absurd values
        invalid = (
            beam is None
            or beam.energy < 1000
            or np.any(np.array(beam.widths) > np.array(raw_image.shape) * 2)
            or np.any(np.array(beam.centroid) > raw_image.shape)
        )

        params = self.parameters

        # Second check: no gaussian fit on major axis
        ellipse = None
        if not invalid:
            # Get (scaled ellipse)
            ellipse = Ellipse.from_beam(beam,
                                        scale=params.axisScale.value)

            _, _, p0, _, _ = fit_gaussian(*ellipse.major_axis)
            invalid = p0 is None

        self.isBeamDetected = not invalid

        if not self.isBeamDetected:
            origin_type = Origin(self.parameters.transform.origin)
            translate = ((0, 0) if origin_type == Origin.NONE
                         else np.divide(raw_image.shape, -2))
            await self._reset(image=np.zeros(raw_image.shape),
                              translate=translate,
                              timestamp=timestamp)
            return

        # Set transform
        origin_type = Origin(params.transform.origin)
        x0, y0 = np.multiply(get_origin(beam, origin_type), -1)
        self._set_transform(translate=[x0, y0])

        # Set properties
        self._set_properties(beam, timestamp)

        # Set axes data
        self._set_axis(ellipse.major_axis, name='majorAxis', translate=x0)
        self._set_axis(ellipse.minor_axis, name='minorAxis', translate=x0)
        self._set_axis(ellipse.x_axis, name='xAxis', translate=x0)
        self._set_axis(ellipse.y_axis, name='yAxis', translate=x0)

        # Send masked image to output channel
        output = self.output
        output.schema.data.image = ImageData(ellipse.masked_image,
                                             timestamp=timestamp)
        await output.writeData(timestamp=timestamp)

    @input.endOfStream
    async def input(self, channelName):
        if self.state != State.ON:
            self.state = State.ON

    @input.close
    async def input(self, channelName):
        self.state = State.ON

    # Extended information

    parameters = Node(
        ParametersNode,
        displayedName="Parameters",
        description="The user input parameters.",
        assignment=Assignment.MANDATORY,
    )

    isBeamDetected = Bool(
        displayedName="Beam Detected?",
        accessMode=AccessMode.READONLY,
        defaultValue=False,
    )

    lastUpdated = String(
        displayedName="Last Updated",
        description="Timestamp when the properties were last updated.",
        accessMode=AccessMode.READONLY,
    )

    beamProperties = Node(
        PropertiesNode,
        displayedName="Beam Properties",
        description="The beam properties of the detected beam."
    )

    majorAxis = Node(
        GaussianNode,
        displayedName="Major Axis",
    )

    minorAxis = Node(
        GaussianNode,
        displayedName="Minor Axis",
    )

    xAxis = Node(
        GaussianNode,
        displayedName="X Axis",
    )

    yAxis = Node(
        GaussianNode,
        displayedName="Y Axis",
    )

    def __init__(self, configuration):
        super().__init__(configuration)
        self.output.noInputShared = "drop"
        self.input.dataDistribution = "copy"
        self.input.onSlowness = "drop"
        self.input.delayOnInput = 1

    # Output channel settings
    output = OutputChannel(
        ChannelNode,
        displayedName="Output",
        description="Output channel of pipeline.")

    def detect_beam(self, image):
        try:
            beam = Beam.detect(image)
        except RuntimeError:
            # Failed to detect the beam
            beam = None

        return beam

    async def _reset(self, *, image, translate, timestamp=None):
        # Reset transform
        self._set_transform(translate=translate)

        # Reset beam properties
        props = {
            'energy': create_value(np.nan, timestamp),

            'x0': create_value(np.nan, timestamp),
            'y0': create_value(np.nan, timestamp),

            'a': create_value(np.nan, timestamp),
            'b': create_value(np.nan, timestamp),
            'majorAxisScaled': create_value(np.nan, timestamp),
            'minorAxisScaled': create_value(np.nan, timestamp),

            'theta': create_value(np.nan, timestamp, units=unit.degrees),

            'peakX': create_value(np.nan, timestamp),
            'peakY': create_value(np.nan, timestamp),
            'peak': create_value(np.nan, timestamp),
        }
        self._set_beam(props)

        # Reset axis
        self._set_axis((np.array([]), np.array([])), name='majorAxis')
        self._set_axis((np.array([]), np.array([])), name='minorAxis')
        self._set_axis((np.array([]), np.array([])), name='xAxis')
        self._set_axis((np.array([]), np.array([])), name='yAxis')

        # Send masked image to output channel
        output = self.output
        output.schema.data.image = ImageData(image, timestamp=timestamp)
        await output.writeData(timestamp=timestamp)

    @slot
    def requestScene(self, params):
        name = params.get('name', default='overview')
        payload = Hash('success', True, 'name', name,
                       'data', get_scene(self.deviceId))

        return Hash('type', 'deviceScene',
                    'origin', self.deviceId,
                    'payload', payload)
