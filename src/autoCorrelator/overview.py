from karabo.common.scenemodel.api import (
    BoxLayoutModel, ComboBoxModel, DisplayCommandModel,
    DisplayLabelModel, DisplayImageModel, DeviceSceneLinkModel,
    DisplayStateColorModel, DisplayPlotModel, DisplayTextLogModel, 
    DoubleLineEditModel, FixedLayoutModel, LabelModel,
    LampModel, LineModel, RectangleModel, SceneLinkModel,
    SceneModel, SceneTargetWindow,
    write_scene)


def generate_scene(device):

    device_id = device["deviceId"]

    device_label = LabelModel(
        font='Ubuntu,15,-1,5,75,0,0,0,0,0', foreground='#000000', 
        height=30, width=500, x=250, y=20,
        text=f'DeviceID: {device_id}')

    # camera device
    input_node = device["input"]
    camera_id = input_node["connectedOutputChannels"]
    if camera_id:
        camera_id = camera_id[0].split(":")[0]
    camera_label = f"Camera: {camera_id}"
    cam_link = DeviceSceneLinkModel(
        keys=[f"{camera_id}.availableScenes"],
        target_window=SceneTargetWindow.Dialog,
        parent_component='DisplayComponent', target='scene',
        text=camera_label,
        x=50, y=70, width=400, height=30)
    img_scene = DisplayImageModel(
        x=10, y=100, height=320, width=650,
        keys=[f'{camera_id}.output.schema.data.image'],
        parent_component='DisplayComponent')
    cam_scene = FixedLayoutModel(
        height=391.0, width=803.0, x=65.0, y=1.0,
        children=[cam_link, img_scene])

    fit_scene = DisplayPlotModel(
        height=363.0, width=800, x=11.0, y=400,
        keys=[f'{device_id}.output.schema.data.profileX',
              f'{device_id}.output.schema.data.profileXFit'],
        parent_component='DisplayComponent')

    # operator
    cmd_width = 510
    state = DisplayLabelModel(
        height=30, width=cmd_width, x=775, y=70,
        keys=[f'{device_id}.state'],
        parent_component='DisplayComponent')

    calib_acquire_01 = DisplayCommandModel(
        height=24.0, width=cmd_width, x=775, y=100,
        keys=[f'{device_id}.useAsCalibrationImage1'],
        parent_component='DisplayComponent')
    calib_acquire_02 = DisplayCommandModel(
        height=24.0, width=cmd_width, x=775, y=130,
        keys=[f'{device_id}.useAsCalibrationImage2'],
        parent_component='DisplayComponent')
    calib_do = DisplayCommandModel(
         height=24.0, width=cmd_width, x=775, y=160,
         keys=[f'{device_id}.calibrate'],
         parent_component='DisplayComponent')
    calib_scene = FixedLayoutModel(
         children=[calib_acquire_01, calib_acquire_02, calib_do])

    x1 = 775
    width1 = 230
    x2 = 990
    width2 = 140
    x3 = 1130
    width3 = 140
    delay_unit_label = LabelModel(
        font='Ubuntu,11,-1,5,50,0,0,0,0,0', foreground='#000000',
        height=27, width=width1, x=x1, y=200,
        parent_component='DisplayComponent', text='Delay Unit')
    delay_unit_get = DisplayLabelModel(
        height=27, width=width2, x=x2, y=200,
        keys=[f'{device_id}.delayUnit'],
        parent_component='DisplayComponent')
    delay_unit_set = ComboBoxModel(
        height=27.0, width=width3, x=x3, y=200,
        keys=[f'{device_id}.delayUnit'],
        klass='EditableComboBox',
        parent_component='EditableApplyLaterComponent')

    delay_value_label = LabelModel(
        font='Ubuntu,11,-1,5,50,0,0,0,0,0', foreground='#000000',
        height=27.0, width=width1, x=x1, y=230,
        parent_component='DisplayComponent', text='Delay ([fs] or [um])')
    delay_value_get = DisplayLabelModel(
        height=27.0, width=width2, x=x2, y=230,
        keys=[f'{device_id}.delay'],
        parent_component='DisplayComponent')
    delay_value_set = DoubleLineEditModel(
        height=27, width=width3, x=x3, y=230,
        keys=[f'{device_id}.delay'],
        parent_component='EditableApplyLaterComponent')
    
    constant_label = LabelModel(
        font='Ubuntu,11,-1,5,50,0,0,0,0,0', foreground='#000000',
        height=27.0, width=width1, x=x1, y=260,
        parent_component='DisplayComponent',
        text='Calibration constant [fs/px]')
    constant_get = DisplayLabelModel(
        height=27.0, width=width2, x=x2, y=260,
        keys=[f'{device_id}.calibrationFactor'],
        parent_component='DisplayComponent')
    constant_set = DoubleLineEditModel(
        height=27, width=width3, x=x3, y=260,
        keys=[f'{device_id}.calibrationFactor'],
        parent_component='EditableApplyLaterComponent')

    beam_label = LabelModel(
        font='Ubuntu,11,-1,5,50,0,0,0,0,0', foreground='#000000',
        height=17.0, width=width1, x=x1, y=290,
        parent_component='DisplayComponent', text='Beam Shape')
    beam_get = DisplayLabelModel(
        height=23.0, width=width2, x=x2, y=290,
        keys=[f'{device_id}.beamShape'],
        parent_component='DisplayComponent')
    beam_set = ComboBoxModel(
        height=27.0, width=width3, x=x3, y=290,
        keys=[f'{device_id}.beamShape'],
        klass='EditableComboBox',
        parent_component='EditableApplyLaterComponent')
    calib_par_scene = FixedLayoutModel(
        children=[delay_unit_label, delay_unit_get, delay_unit_set,
                  delay_value_label, delay_value_get, delay_value_set,
                  constant_label, constant_get, constant_set,
                  beam_label, beam_get, beam_set])

    # result
    x1 = 850
    width1 = 200
    x2 = 1000
    width2 = 100
    result_label = LabelModel(
        font='Ubuntu,11,-1,5,50,0,0,0,0,0', foreground='#000000',
        height=17.0, width=width1, x=x1, y=510,
        parent_component='DisplayComponent', text='Pulse Duration')
    result = DisplayLabelModel(
        height=23.0, width=width2, x=x2, y=510,
        keys=[f'{device_id}.pulseWidth'],
        parent_component='DisplayComponent')
    result_error_label = LabelModel(
        font='Ubuntu,11,-1,5,50,0,0,0,0,0', foreground='#000000',
        height=17.0, width=width1, x=x1, y=550,
        parent_component='DisplayComponent', text='Uncertainty')
    result_error = DisplayLabelModel(
        height=23.0, width=width2, x=x2, y=550,
        keys=[f'{device_id}.ePulseWidth'],
        parent_component='DisplayComponent')
    fit_status_label = LabelModel(
        font='Ubuntu,11,-1,5,50,0,0,0,0,0', foreground='#000000',
        height=17.0, width=width1, x=x1, y=590,
        parent_component='DisplayComponent', text='Fit Status')
    fit_status = DisplayLabelModel(
        height=23.0, width=width2, x=x2, y=590,
        keys=[f'{device_id}.fitError'],
        parent_component='DisplayComponent')
    result_scene = FixedLayoutModel(
         height=761.0, width=1342.0,
        children=[result_label, result,
                  result_error_label, result_error,
                  fit_status_label, fit_status])

    op_scene = FixedLayoutModel(
         height=761.0, width=1342.0,
         children=[state, calib_scene, calib_par_scene])

    scene = SceneModel(
        height=800, width=1100,
        children=[device_label, cam_scene, fit_scene,
                  op_scene, result_scene])

    return write_scene(scene)
