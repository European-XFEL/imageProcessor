#############################################################################
# Author: carinanc
# Created on May 26, 2021, 03:08 PM
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################

import numpy as np

from karabo.middlelayer import (
    AccessMode, Bool, Configurable, DaqDataType, Double, Encoding, Image,
    ImageData, Node, String, UInt16, Unit, VectorFloat, VectorHash)

from .const import DTYPE, Origin

# -----------------------------------------------------------------------------
# Parameters node


class TransformNode(Configurable):

    pixelScale = Double(
        displayedName="Pixel Scale Factor",
        description="Converts pixels to physical units"
                    " for ticks and derived values (e.g., 2 mm/pixel → 2)",
        defaultValue=1.0,
        minExc=0.0,
    )

    pixelTranslate = VectorFloat(
        displayedName="Pixel Translate Factor",
        description="Translation for both x- and y-axis.",
        defaultValue=[0.0, 0.0],
        minSize=2, maxSize=2,
        accessMode=AccessMode.READONLY,
    )

    origin = String(
        displayedName="Origin",
        options=Origin.as_list(),
        defaultValue=Origin.index(0),
    )

    beamWidthScale = Double(
        displayedName="Beam Width Scale",
        description="Scale factor for the beam width.",
        defaultValue=1.0,
    )

    def set_translate(self, x0, y0):
        if not np.allclose((x0, y0), self.pixelTranslate.value):
            self.pixelTranslate = [x0, y0]


class ParametersNode(Configurable):
    # Input parameters

    # Deprecate ROIs for the meantime.
    # Not sure if this is being used.
    # @VectorUInt32(
    #     defaultValue=list(DEFAULT_ROI),
    #     displayedName="Region of Interest",
    #     description=(
    #         "The user-defined range for centre-of-mass. "
    #         "Region [lowX, highX) x [lowY, highY) "
    #         "specified as [lowX, highX, lowY, highY]. "
    #         f"Defaults to {DEFAULT_ROI}, which uses the whole image."),
    #     minSize=4, maxSize=4)
    # def roi(self, value):
    #     x_low, x_high, y_low, y_high = value
    #     if x_low > x_high:
    #         x_low, x_high = x_high, x_low
    #     if y_low > y_high:
    #         y_low, y_high = y_high, y_low
    #     self.roi = roi = [x_low.value, x_high.value,
    #                       y_low.value, y_high.value]
    #     self.has_roi = tuple(roi) != DEFAULT_ROI

    axisScale = Double(
        displayedName="Axis Scale Factor",
        description="Scale factor displaying the major/minor axes.",
        defaultValue=2.0,
        minInc=0.0,
    )

    inhomogeneousBackgroundSamples = UInt16(
        displayedName="Inhomogeneous Background Samples",
        description="Number of pixels that are sampled from the "
                    "top and bottom of the image.",
        defaultValue=0,
        unitSymbol=Unit.PIXEL,
    )

    energyScale = Double(
        displayedName="Energy Scale Factor",
        description="Scale factor for the integrated region.",
        defaultValue=1.0e2,
        minInc=1.0,
    )

    isSuperGaussian = Bool(
        displayedName="Use Super Gaussian",
        defaultValue=False,
    )

    width = Double(
        displayedName="Width Scale",
        defaultValue=1.0,
        minInc=0.0
    )

    transform = Node(
        TransformNode,
        displayedName="Transform"
    )

    def __init__(self, config):
        super().__init__(config)
        self.has_roi = False


# -----------------------------------------------------------------------------
# Extended information nodes


class PropertiesNode(Configurable):

    energy = Double(
        displayedName="Integral Over Region",
        description="Integral of pixel values.",
        unitSymbol=Unit.NUMBER,
        accessMode=AccessMode.READONLY,
    )

    x0 = Double(
        displayedName="x0 (Centre-Of-Mass)",
        description="X position of the centre-of-mass.",
        accessMode=AccessMode.READONLY,
    )

    y0 = Double(
        displayedName="y0 (Centre-Of-Mass)",
        description="Y position of the centre-of-mass.",
        accessMode=AccessMode.READONLY,
    )

    a = Double(
        displayedName="Major Axis (a)",
        description="Major axis of the beam ellipse.",
        accessMode=AccessMode.READONLY,
    )

    b = Double(
        displayedName="Minor Axis (b)",
        description="Minor axis of the beam ellipse.",
        accessMode=AccessMode.READONLY,
    )

    majorAxisScaled = Double(
        displayedName="Scaled Major Axis (a)",
        description="Major axis of the beam ellipse, scaled.",
        accessMode=AccessMode.READONLY,
    )

    minorAxisScaled = Double(
        displayedName="Scaled Minor Axis (b)",
        description="Minor axis of the beam ellipse, scaled.",
        accessMode=AccessMode.READONLY,
    )

    theta = Double(
        displayedName="Rotation Angle",
        description="Rotation angle of the beam ellipse.",
        unitSymbol=Unit.DEGREE,
        accessMode=AccessMode.READONLY,
    )

    peak = Double(
        displayedName="Max Pixel Value",
        description="The maximum image pixel value.",
        unitSymbol=Unit.NUMBER,
        accessMode=AccessMode.READONLY,
    )

    peakX = Double(
        displayedName="x0 (Max-Pixel)",
        description="X position of the maximum pixel value.",
        accessMode=AccessMode.READONLY,
    )

    peakY = Double(
        displayedName="y0 (Max-Pixel)",
        description="Y position of the maximum pixel value.",
        accessMode=AccessMode.READONLY,
    )

    ex01d = Double(
        displayedName="sigma(x0)",
        description="Uncertainty on x0 estimation.",
        accessMode=AccessMode.READONLY,
    )

    ey01d = Double(
        displayedName="sigma(y0)",
        description="Uncertainty on y0 estimation.",
        accessMode=AccessMode.READONLY,
    )


class GaussianNode(Configurable):
    pos = Double(
        unitSymbol=Unit.NUMBER,
        accessMode=AccessMode.READONLY,
    )

    width = Double(
        unitSymbol=Unit.NUMBER,
        accessMode=AccessMode.READONLY
    )

    r2 = Double(
        unitSymbol=Unit.NUMBER,
        accessMode=AccessMode.READONLY,
    )

    uncertainty = Double(
        unitSymbol=Unit.NUMBER,
        accessMode=AccessMode.READONLY,
    )


# -----------------------------------------------------------------------------
# Output channel nodes

class ReadOnlyTransformNode(Configurable):
    pixelScale = Double(
        displayedName="Pixel Scale Factor",
        description="Converts pixels to physical units for"
                    " ticks and derived values (e.g., 2 mm/pixel → 2)",
        defaultValue=1.0,
        minExc=0.0,
        accessMode=AccessMode.READONLY,
    )

    pixelTranslate = VectorFloat(
        displayedName="Pixel Translate Factor",
        description="Translation for both x- and y-axis",
        defaultValue=[0.0, 0.0],
        minSize=2, maxSize=2,
        accessMode=AccessMode.READONLY,
    )


class AxisRowSchema(Configurable):
    label = String(accessMode=AccessMode.READONLY)
    plotType = String(accessMode=AccessMode.READONLY)
    x = VectorFloat(accessMode=AccessMode.READONLY)
    y = VectorFloat(accessMode=AccessMode.READONLY)


class DataNode(Configurable):
    daqDataType = DaqDataType.TRAIN
    displayType = 'WidgetNode|BeamGraph'

    image = Image(data=ImageData(np.zeros((100, 100), dtype=DTYPE),
                                 encoding=Encoding.GRAY),
                  displayedName="Image")

    beamProperties = Node(
        PropertiesNode,
        displayedName="Beam Properties",
        description="The beam properties of the detected beam."
    )

    transform = Node(
        ReadOnlyTransformNode,
        displayedName="Transform",
        description="Contains image scale and translate factors."
    )

    inhomogeneousBackground = VectorHash(
        rows=AxisRowSchema,
        defaultValue=[],
        displayedName="Inhomogeneous Background",
        displayType="TableVectorXYGraph",
        accessMode=AccessMode.READONLY)

    majorAxis = VectorHash(
        rows=AxisRowSchema,
        defaultValue=[],
        displayedName="Major Axis",
        displayType="TableVectorXYGraph",
        accessMode=AccessMode.READONLY)

    minorAxis = VectorHash(
        rows=AxisRowSchema,
        defaultValue=[],
        displayedName="Minor Axis",
        displayType="TableVectorXYGraph",
        accessMode=AccessMode.READONLY)

    xAxis = VectorHash(
        rows=AxisRowSchema,
        defaultValue=[],
        displayedName="X Axis",
        displayType="TableVectorXYGraph",
        accessMode=AccessMode.READONLY)

    yAxis = VectorHash(
        rows=AxisRowSchema,
        defaultValue=[],
        displayedName="Y Axis",
        displayType="TableVectorXYGraph",
        accessMode=AccessMode.READONLY)


class ChannelNode(Configurable):
    data = Node(DataNode)
