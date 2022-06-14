from karabo.common.scenemodel.api import (
    CheckBoxModel, ComboBoxModel, DisplayCommandModel,
    DisplayImageModel, DisplayLabelModel, DeviceSceneLinkModel,
    DisplayPlotModel, DisplayTextLogModel,
    DoubleLineEditModel, IntLineEditModel, LabelModel, LineModel,
    SceneModel, SceneTargetWindow, write_scene)

KEY_LABEL_FONT = 'Ubuntu,11,-1,5,50,0,0,0,0,0'


def generate_scene(device):

    widgets = []
    device_id = device["deviceId"]

    widgets.append(LabelModel(
        font='Ubuntu,17,-1,5,75,0,0,0,0,0', foreground='#000000',
        height=30, width=500, x=350, y=20,
        text=device_id))

    # camera device
    input_node = device["input"]
    camera_id = input_node["connectedOutputChannels"]
    if camera_id:
        camera_id = camera_id[0].split(":")[0]
    camera_label = "Camera Scene"

    line_x = 580
    widgets.append(DeviceSceneLinkModel(
        keys=[f"{camera_id}.availableScenes"],
        target_window=SceneTargetWindow.Dialog,
        parent_component='DisplayComponent', target='scene',
        text=camera_label,
        x=50, y=70, width=150, height=30))
    widgets.append(DisplayPlotModel(
        x=10, y=450,
        height=320, width=550,
        keys=[f'{device_id}.output.schema.data.integralX',
              f'{device_id}.output.schema.data.integralXFit'],
        parent_component='DisplayComponent'))
    widgets.append(DisplayImageModel(
        x=10, y=100, height=320, width=550,
        keys=[f'{camera_id}.output.schema.data.image'],
        parent_component='DisplayComponent'))

    widgets.append(LineModel(
        stroke='#000000', stroke_width=2.0,
        x=line_x, x1=line_x, x2=line_x, y=60, y1=80, y2=750))

    width = 170
    x1 = line_x + 20
    x2 = x1 + width
    x3 = x2 + width
    # operator
    cmd_width = width * 3
    widgets.append(DisplayLabelModel(
        height=30, width=cmd_width, x=x1, y=80,
        keys=[f'{device_id}.state'],
        parent_component='DisplayComponent'))

    commands = ("useAsCalibrationImage1", "useAsCalibrationImage2",
                "calibrate")
    y = 120
    for cmd in commands:
        widgets.append(DisplayCommandModel(
            height=24.0, width=cmd_width, x=x1, y=y,
            keys=[f'{device_id}.{cmd}'],
            parent_component='DisplayComponent'))
        y += 30

    dikt = {"combo": {"model": ComboBoxModel,
                      "klass": "EditableComboBox",
                      "keys": {"beamShape": "Beam Shape",
                               "delayUnit": "Delay Unit"}},
            "check": {"model": CheckBoxModel,
                      "klass": "EditableCheckBox",
                      "keys": {'subtractPedestal': "Subtract Pedestal"}},
            "fedit": {"model": DoubleLineEditModel,
                      "klass": None,
                      "keys": {
                          "delay": "Delay ([fs] or [um])",
                          "calibrationFactor": "Calibration Const. [fs/px]"}},
            "iedit": {"model": IntLineEditModel,
                      "klass": None,
                      "keys": {
                          "xMinFit": "Fit Lower Limit",
                          "xMaxFit": "Fit Upper Limit"}},
            "read": {"model": None,
                     "klass": None,
                     "keys": {
                         "pulseWidth": "Pulse Duration",
                         "ePulseWidth": "Fit Uncertainty",
                         "fitStatus": "Fit Status"}}}
    y += 30
    for obj in dikt:
        subdikt = dikt[obj]
        klass = subdikt["klass"]
        model = subdikt["model"]
        keys = subdikt["keys"]
        for key in keys:
            label = keys[key]
            widgets.append(LabelModel(
                font=KEY_LABEL_FONT, foreground='#000000',
                height=23, width=width, x=x1, y=y,
                parent_component='DisplayComponent', text=label))
            widgets.append(DisplayLabelModel(
                height=23, width=width, x=x2, y=y,
                keys=[f'{device_id}.{key}'],
                parent_component='DisplayComponent'))
            if obj == "read":  # no edit widgets for these keys
                y += 30
                continue
            if klass:
                widgets.append(model(
                    height=23, width=width, x=x3, y=y,
                    keys=[f'{device_id}.{key}'],
                    klass=klass,
                    parent_component='EditableApplyLaterComponent'))
            else:
                widgets.append(model(
                    height=23, width=width, x=x3, y=y,
                    keys=[f'{device_id}.{key}'],
                    parent_component='EditableApplyLaterComponent'))
            y += 30

    widgets.append(LabelModel(
        font='Ubuntu,12,-1,5,75,0,0,0,0,0', foreground='#000000',
        height=38.0, width=width, x=x2, y=540,
        parent_component='DisplayComponent', text='Status'))
    widgets.append(DisplayTextLogModel(
        height=210, width=cmd_width, x=x1, y=565,
        keys=[f'{device_id}.status'],
        parent_component='DisplayComponent'))

    scene = SceneModel(height=800, width=1150, children=widgets)

    return write_scene(scene)
