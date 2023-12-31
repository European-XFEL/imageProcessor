#############################################################################
# Author: parenti
# Created on April 16, 2019, 02:56 PM
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

import time

from image_processing import crosshair, imageArbitraryRotation
from karabo.bound import (
    BOOL_ELEMENT, DOUBLE_ELEMENT, IMAGEDATA_ELEMENT, INPUT_CHANNEL,
    KARABO_CLASSINFO, NODE_ELEMENT, OUTPUT_CHANNEL, OVERWRITE_ELEMENT,
    STRING_ELEMENT, UINT32_ELEMENT, UINT64_ELEMENT, VECTOR_UINT32_ELEMENT,
    DaqDataType, DeviceClient, Hash, ImageData, PythonDevice, Schema, State,
    Timestamp, Types, Unit)
from processing_utils.rate_calculator import RateCalculator

from ._version import version as deviceVersion

NR_OF_CHANNELS = 2


@KARABO_CLASSINFO("ImagePatternPicker", deviceVersion)
class ImagePatternPicker(PythonDevice):

    @staticmethod
    def expectedParameters(expected):
        (
            OVERWRITE_ELEMENT(expected).key('state')
            .setNewOptions(State.ON, State.PROCESSING, State.ERROR)
            .setNewDefaultValue(State.ON)
            .commit()
        )

        for idx in range(NR_OF_CHANNELS):
            channel = f"chan_{idx}"
            ImagePatternPicker.create_channel_node(expected, channel)

    def __init__(self, configuration):
        # always call PythonDevice constructor first!
        super(ImagePatternPicker, self).__init__(configuration)

        self.device_client = DeviceClient()

        self.frame_rate_in = []
        self.frame_rate_out = []
        self.connections = {}
        self.last_train_id = {}
        self.last_bad_tid_time = {}

        self.preReconfigure(configuration)  # Apply initial configuration

        # Define the first function to be called after the constructor has
        # finished
        self.registerInitialFunction(self.initialization)

    def initialization(self):
        self.device_client.getDevices()  # Somehow needed to connect

        for idx in range(NR_OF_CHANNELS):
            chan = f"chan_{idx}"
            input_chan = f"{chan}.input.connectedOutputChannels"
            try:
                inputs = self[input_chan]
                if inputs:

                    # Register call-backs
                    self.KARABO_ON_DATA(f"{chan}.input", self.onData)
                    self.KARABO_ON_EOS(f"{chan}.input", self.onEndOfStream)

                    # Variables for frames per second computation
                    self.frame_rate_in.append(
                        RateCalculator(refresh_interval=1.0))
                    self.frame_rate_out.append(
                        RateCalculator(refresh_interval=1.0))

                    # TODO how to treat the case len(inputs) > 1?
                    device_id, connected_pipe = inputs[0].split(':')
                    # in case we have an input device, let us put
                    # its features in the dictionary. The key will be
                    # an increasing integer
                    if device_id:
                        output_image = \
                            f"{connected_pipe}.schema.data.image"
                        self.connections[idx] = {
                            # the device in input
                            "device_id": device_id,
                            # the used output of device
                            "input_pipeline": connected_pipe,
                            # the corresponding output image
                            "output_image": output_image,
                        }
                        self.device_client.registerSchemaUpdatedMonitor(
                            self.on_camera_schema_update)
                        self.device_client.getDeviceSchemaNoWait(device_id)
            except Exception as e:
                self.log.ERROR(f"Error Exception: {e}")

    def preReconfigure(self, configuration):
        for idx in range(NR_OF_CHANNELS):
            node = f"chan_{idx}"
            if f'{node}.enableCrosshair' in configuration:
                enable = configuration[f'{node}.enableCrosshair']
                warn_crosshair = self[f'{node}.warnCrosshair']
                if enable and warn_crosshair == 0:
                    # raise the warning
                    self[f'{node}.warnCrosshair'] = 1
                elif not enable and warn_crosshair != 0:
                    # cancel the warning
                    self[f'{node}.warnCrosshair'] = 0

            # Synchronize old and new keys for x-hair position.
            # For backward compatibility '{node}.crosshair?' prevails.
            positionX = configuration.get(f'{node}.crosshairX')
            positionY = configuration.get(f'{node}.crosshairY')
            if (positionX, positionY) != (None, None):
                if positionX is None:
                    positionX = self[f'{node}.crosshairX']
                if positionY is None:
                    positionY = self[f'{node}.crosshairY']
                configuration[f'{node}.position'] = [positionX, positionY]
            elif f'{node}.position' in configuration:
                position = configuration[f'{node}.position']
                configuration[f'{node}.crosshairX'] = position[0]
                configuration[f'{node}.crosshairY'] = position[1]

    def is_valid_train_id(self, train_id, node):
        last_train_id = self.last_train_id.get(node, 0)
        last_bad_tid_time = self.last_bad_tid_time.get(node, 0.)
        self.last_train_id[node] = train_id
        warn_train_id = self[f"{node}.warnTrainId"]

        if train_id > last_train_id:
            if warn_train_id != 0 and time.time() - last_bad_tid_time > 1.:
                # no "bad" trainId received in the past 1 s
                self[f"{node}.warnTrainId"] = 0  # remove warning
            status = "Processing"
            is_valid = True
        else:
            self.last_bad_tid_time[node] = time.time()

            if warn_train_id == 0:
                self[f"{node}.warnTrainId"] = 1  # raise warning

            status = "Invalid trainId"
            if train_id == 0:
                status += ": received 0"
            elif train_id < last_train_id:
                status += ": decreasing"
            elif train_id == last_train_id:
                status += ": not increasing"

            is_valid = False

        if self[f"{node}.status"] != status:
            self[f"{node}.status"] = status

        return is_valid

    def onData(self, data, metaData):
        if not self.connections:
            return

        channel = metaData["source"]
        update_dev, update_pipe = channel.split(":")
        ts = Timestamp.fromHashAttributes(
            metaData.getAttributes('timestamp'))
        train_id = ts.getTrainId()

        # find which node the updating device belongs to
        # loop over dictionary of input devices
        for key in list(self.connections.keys()):
            input_dev_block = self.connections[key]
            device_id = input_dev_block["device_id"]
            dev_pipe = input_dev_block["input_pipeline"]

            # updating device is in this block; proceed
            if update_dev == device_id and update_pipe == dev_pipe:
                node = f"chan_{key}"

                self.refresh_frame_rate_in(key)

                # check wheher image has a valid trainId
                if not self.is_valid_train_id(train_id, node):
                    return

                if self['state'] == State.ON:
                    self.updateState(State.PROCESSING)

                if ((train_id % self[f'{node}.nBunchPatterns'])
                        == self[f'{node}.patternOffset']):
                    data['data.trainId'] = train_id

                    need_processing = (
                        self[f'{node}.enableCrosshair']
                        or self[f'{node}.enableRotation'])

                    if not need_processing:
                        # forward image as it is
                        output_data = data
                    else:
                        image_data = data['data.image']
                        image = image_data.getData()  # np.ndarray

                        if self[f'{node}.enableRotation']:
                            # rotate image
                            angle = self[f'{node}.rotationAngle']
                            center = self[f'{node}.rotationCenter']
                            if len(center) != 2:
                                center = None
                            if angle != 0.:
                                image = imageArbitraryRotation(
                                    image, -angle, center)  # clocwise rotation

                        if self[f'{node}.enableCrosshair']:
                            # superimpose a cross-hair
                            x0 = self[f'{node}.crosshairX']
                            y0 = self[f'{node}.crosshairY']
                            center = (x0, y0)

                            if self[f'{node}.crosshairAutoSize']:
                                ext_size = max(10, max(image.shape) // 40)
                            else:
                                ext_size = self[f'{node}.crosshairSize']
                            int_size = ext_size // 3
                            color = round(image.max() // 2)
                            thickness = max(2, ext_size // 5)

                            crosshair(image, center, ext_size, int_size, color,
                                      thickness)

                        image_data = ImageData(image)
                        output_data = Hash('data.image', image_data)

                    self.writeChannel(f"{node}.output", output_data, ts)
                    self.refresh_frame_rate_out(key)

    def onEndOfStream(self, inputChannel):
        connected_devices = inputChannel.getConnectedOutputChannels().keys()
        dev = [*connected_devices][0]

        # find which node the updating device belongs to
        stopped_nodes = 0
        for key in list(self.connections.keys()):
            input_dev_block = self.connections[key]
            device_id = input_dev_block["device_id"]

            if device_id == dev.split(":")[0]:
                node = f"chan_{key}"
                self.log.INFO("onEndOfStream called")
                self[f"{node}.status"] = "Idle"
                self[f"{node}.inFrameRate"] = 0.
                self[f"{node}.outFrameRate"] = 0.
                # Signals end of stream
                self.signalEndOfStream(f"{node}.output")
                stopped_nodes += 1

        # state should be ON if all cameras are not acquiring
        if stopped_nodes == len(self.connections):
            self.updateState(State.ON)

    def refresh_frame_rate_in(self, channel_idx):
        frame_rate = self.frame_rate_in[channel_idx]
        frame_rate.update()
        fps_in = frame_rate.refresh()
        if fps_in:
            self[f"chan_{channel_idx}.inFrameRate"] = fps_in
            self.log.DEBUG(f"Channel {channel_idx}: Input rate {fps_in} Hz")

    def refresh_frame_rate_out(self, channel_idx):
        frame_rate = self.frame_rate_out[channel_idx]
        frame_rate.update()
        fps_out = frame_rate.refresh()
        if fps_out:
            self[f"chan_{channel_idx}.outFrameRate"] = fps_out
            self.log.DEBUG(f"Channel {channel_idx}: Output rate {fps_out} Hz")

    def on_camera_schema_update(self, deviceId, schema):
        # find all inputs connected to this updating schema device
        channels_key = [key for key in list(self.connections.keys())
                        if deviceId
                        == self.connections[key]["device_id"]]

        # loop over connected inputs
        for key in channels_key:
            node = f"chan_{key}"
            # Look for 'image' in camera's schema
            path = self.connections[key]["output_image"]
            if schema.has(path):
                sub = schema.subSchema(path)
                shape = sub.getDefaultValue('dims')
                k_type = sub.getDefaultValue('pixels.type')
                self.update_output_schema(node, shape, k_type)

    @staticmethod
    def create_channel_node(schema, channel,
                            shape=(), k_type=Types.NONE, skip_input=False):
        data_in = Schema()
        data_out = Schema()
        idx = channel.replace("chan_", "")

        (
            NODE_ELEMENT(schema)
            .key(channel)
            .displayedName(f"Channel {idx}")
            .commit(),

            UINT32_ELEMENT(schema)
            .key(f"{channel}.nBunchPatterns")
            .displayedName("# Bunch Patterns")
            .description("Number of bunch patterns.")
            .assignmentOptional().defaultValue(2)
            .minInc(1)
            .reconfigurable()
            .commit(),

            UINT32_ELEMENT(schema)
            .key(f"{channel}.patternOffset")
            .displayedName("Pattern Offset")
            .description("Image will be forwarded to the output if its "
                         "trainId satisfies the following relation: "
                         "(trainId%nBunchPatterns) ==  patternOffset.")
            .assignmentOptional().defaultValue(1)
            .reconfigurable()
            .commit(),

            BOOL_ELEMENT(schema).key(f"{channel}.enableCrosshair")
            .displayedName("Enable Crosshair")
            .assignmentOptional().defaultValue(False)
            .reconfigurable()
            .commit(),

            STRING_ELEMENT(schema).key(f"{channel}.status")
            .displayedName("Status")
            .readOnly().initialValue("")
            .commit(),

            UINT32_ELEMENT(schema).key(f"{channel}.warnCrosshair")
            .displayedName("Crosshair Warning")
            .description("Raise a warning when cross-hair is enabled.")
            .readOnly().initialValue(0)
            .warnHigh(0).info("Cross-hair is enabled! Disable before saving "
                              "images to DAQ or use them for processing.")
            .needsAcknowledging(False)
            .commit(),

            UINT32_ELEMENT(schema).key(f"{channel}.warnTrainId")
            .displayedName("Invalid TrainId")
            .description("Raise a warning when image's trainId is invalid: 0, "
                         "decreasing or not increasing.")
            .readOnly().initialValue(0)
            .warnHigh(0).info("Image's trainId is invalid! It is 0, "
                              "decreasing or not increasing.")
            .needsAcknowledging(False)
            .commit(),

            # Old property - for backward compatibility
            UINT32_ELEMENT(schema).key(f"{channel}.crosshairX")
            .displayedName("Crosshair X position")
            .description("The X position of the crosshair.")
            .assignmentOptional().defaultValue(0)
            .unit(Unit.PIXEL)
            .adminAccess()
            .reconfigurable()
            .commit(),

            # Old property - for backward compatibility
            UINT32_ELEMENT(schema).key(f"{channel}.crosshairY")
            .displayedName("Crosshair Y position")
            .description("The Y position of the crosshair.")
            .assignmentOptional().defaultValue(0)
            .adminAccess()
            .unit(Unit.PIXEL)
            .reconfigurable()
            .commit(),

            # New property to be used by xhair widget
            VECTOR_UINT32_ELEMENT(schema).key(f"{channel}.position")
            .setSpecialDisplayType("crosshair")
            .displayedName("Crosshair Position")
            .description("The position of the crosshair: [X, Y].")
            .assignmentOptional().defaultValue([0, 0])
            .minSize(2).maxSize(2)
            .adminAccess()
            .unit(Unit.PIXEL)
            .reconfigurable()
            .commit(),

            BOOL_ELEMENT(schema).key(f"{channel}.crosshairAutoSize")
            .displayedName("Crosshair Auto-Size")
            .description("The crosshair size will be calculated from the "
                         "image size.")
            .assignmentOptional().defaultValue(True)
            .reconfigurable()
            .commit(),

            UINT32_ELEMENT(schema).key(f"{channel}.crosshairSize")
            .displayedName("Cross-Hair Size")
            .description("The crosshair size. This property will be ignored "
                         "if the 'Auto-Size' option is selected.")
            .assignmentOptional().defaultValue(30)
            .unit(Unit.PIXEL)
            .reconfigurable()
            .commit(),

            BOOL_ELEMENT(schema).key(f"{channel}.enableRotation")
            .displayedName("Enable Rotation")
            .assignmentOptional().defaultValue(False)
            .reconfigurable()
            .commit(),

            VECTOR_UINT32_ELEMENT(schema).key(f"{channel}.rotationCenter")
            .displayedName("Rotation Center")
            .description("Leave empty to rotate around the image center.")
            .assignmentOptional().defaultValue([])
            .maxSize(2)
            .reconfigurable()
            .commit(),

            DOUBLE_ELEMENT(schema).key(f"{channel}.rotationAngle")
            .displayedName("Rotation Angle")
            .description("The image rotation angle (clockwise).")
            .assignmentOptional().defaultValue(0)
            .minInc(-15.).maxInc(15.)
            .unit(Unit.DEGREE)
            .reconfigurable()
            .commit(),

            DOUBLE_ELEMENT(schema)
            .key(f"{channel}.inFrameRate")
            .displayedName('Input Frame Rate')
            .description('The input frame rate.')
            .unit(Unit.HERTZ)
            .readOnly()
            .commit(),

            DOUBLE_ELEMENT(schema)
            .key(f"{channel}.outFrameRate")
            .displayedName('Output Frame Rate')
            .description('The output frame rate.')
            .unit(Unit.HERTZ)
            .readOnly()
            .commit(),
        )

        if not skip_input:
            (
                NODE_ELEMENT(data_in)
                .key("data")
                .displayedName("Data")
                .commit(),

                IMAGEDATA_ELEMENT(data_in)
                .key("data.image")
                .displayedName("Image")
                .commit(),

                INPUT_CHANNEL(schema)
                .key(f"{channel}.input")
                .displayedName("Input")
                .dataSchema(data_in)
                .commit(),
            )

        (
            NODE_ELEMENT(data_out)
            .key('data')
            .displayedName("Data")
            .setDaqDataType(DaqDataType.TRAIN)
            .commit(),

            IMAGEDATA_ELEMENT(data_out)
            .key('data.image')
            .displayedName("Image")
            .setDimensions(list(shape))
            .setType(Types.values[k_type])
            .commit(),

            UINT64_ELEMENT(data_out)
            .key('data.trainId')
            .displayedName('Train ID')
            .readOnly()
            .commit(),

            OUTPUT_CHANNEL(schema)
            .key(f"{channel}.output")
            .displayedName("Output")
            .dataSchema(data_out)
            .commit(),
        )

    def update_output_schema(self, channel, shape, k_type):
        newSchema = Schema()
        ImagePatternPicker.create_channel_node(newSchema, channel, shape,
                                               k_type, skip_input=True)

        self.appendSchema(newSchema)
