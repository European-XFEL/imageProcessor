from karabo.common.scenemodel.api import (
    BoxLayoutModel, DeviceSceneLinkModel,
    DisplayLabelModel, DisplayImageModel, DisplayStateColorModel, DisplayPlotModel, DisplayTextLogModel, 
    FixedLayoutModel, LabelModel,
    LampModel, LineModel, RectangleModel, SceneLinkModel,
    SceneModel, SceneTargetWindow,
    write_scene)

BEAMLINE_SIZE = 35
OUTPUT_LINES_VSPACING = 90
REFERENCE_TOP_Y = 175
REFERENCE_BOTTOM_Y = REFERENCE_TOP_Y + 20 + OUTPUT_LINES_VSPACING * 4
WP_WIDTH = 80
TRAN_WIDTH = 40
DEVICE_WIDTH = 100
OPTIC_SECTION_WIDTH = WP_WIDTH + TRAN_WIDTH + DEVICE_WIDTH + TRAN_WIDTH
START_X = 280


def generate_scene(device):

    deviceId = device

    scene00 = LabelModel(font='Ubuntu,11,-1,5,50,0,0,0,0,0', foreground='#000000', height=499.0, parent_component='DisplayComponent', text='Image', width=43.0, x=125.0, y=117.0)
    scene01 = DisplayImageModel(height=381.0, keys=['LA2_LAS_PPL/CAM/AC_XF2_DIAG.output.schema.data.image'], parent_component='DisplayComponent', width=750.0)
    scene0 = BoxLayoutModel(height=391.0, width=803.0, x=65.0, y=1.0, children=[scene00, scene01])
    scene10 = LabelModel(font='Ubuntu,11,-1,5,50,0,0,0,0,0', foreground='#000000', height=499.0, parent_component='DisplayComponent', text='Image X Profile', width=105.0, x=116.0, y=324.0)
    scene11 = DisplayPlotModel(height=363.0, keys=['LA2_LAS_PPL/CTRL/AC_XF2_DIAG.output.schema.data.profileX', 'LA2_LAS_PPL/CTRL/AC_XF2_DIAG.output.schema.data.profileXFit'], parent_component='DisplayComponent', width=421.0)
    scene1 = BoxLayoutModel(height=373.0, width=779.0, x=11.0, y=375.0, children=[scene10, scene11])
    scene = SceneModel(children=[scene0, scene1])

    return write_scene(scene)
