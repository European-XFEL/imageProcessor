#############################################################################
# Author: parenti
# Created on April 16, 2019, 02:56 PM
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

from karabo.bound import (
    DaqDataType, DeviceClient, DOUBLE_ELEMENT, INPUT_CHANNEL,
    KARABO_CLASSINFO, IMAGEDATA_ELEMENT, NODE_ELEMENT, OUTPUT_CHANNEL,
    OVERWRITE_ELEMENT, PythonDevice, Schema, State, Timestamp, Types,
    UINT32_ELEMENT, UINT64_ELEMENT, Unit
)

from processing_utils.rate_calculator import RateCalculator

NR_OF_CHANNELS = 2


@KARABO_CLASSINFO("ImagePatternPicker", "2.5")
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

        # Define the first function to be called after the constructor has
        # finished
        self.registerInitialFunction(self.initialization)

    def initialization(self):
        self.device_client.getDevices()  # Somehow needed to connect

        for idx in range(NR_OF_CHANNELS):
            chan = "chan_{}".format(idx)
            input_chan = '{}.input.connectedOutputChannels'.format(chan)
            output_image = 'output.schema.data.image'
            try:
                inputs = self[input_chan]
                if inputs:

                    # Register call-backs
                    self.KARABO_ON_DATA("{}.input".format(chan),
                                        self.onData)
                    self.KARABO_ON_EOS("{}.input".format(chan),
                                       self.onEndOfStream)

                    # Variables for frames per second computation
                    self.frame_rate_in.append(
                        RateCalculator(refresh_interval=1.0))
                    self.frame_rate_out.append(
                        RateCalculator(refresh_interval=1.0))

                    connected_chan = inputs[0]
                    device_id = connected_chan.split(":")[0]
                    self.connections[device_id] = {}
                    connected_pipe = connected_chan.split(":")[1]
                    self.connections[device_id]["input_pipeline"] = \
                        connected_pipe
                    # the corresponding output image
                    self.connections[device_id]["output_image"] = output_image
                    # the channel node a device belongs to
                    self.connections[device_id]["channel_node"] = chan
                    if device_id:
                        self.device_client.registerSchemaUpdatedMonitor(
                            self.on_camera_schema_update)
                        self.device_client.getDeviceSchemaNoWait(device_id)
            except Exception as e:
                print("ERROR EXCEPTION: ", e)
            # (KeyError, RuntimeError):
            #    pass

    def onData(self, data, metaData):
        if not self.connections:
            return
        # find channel
        dev = metaData["source"].split(":")[0]
        channel = [self.connections[key]["channel_node"]
                   for key in self.connections.keys() if
                   dev == key][0]
        channel_idx = int(channel.split("_")[1])
        if self['state'] == State.ON:
            self.log.INFO("Start of Stream")
            self.updateState(State.PROCESSING)

        self.refresh_frame_rate_in(channel_idx)

        ts = Timestamp.fromHashAttributes(
            metaData.getAttributes('timestamp'))
        train_id = ts.getTrainId()
        if ((train_id % self['{}.nBunchPatterns'.format(channel)]) ==
                self['{}.patternOffset'.format(channel)]):
            data['data.trainId'.format(channel)] = train_id
            self.writeChannel('{}.output'.format(channel), data, ts)
            self.refresh_frame_rate_out(channel_idx)

    def onEndOfStream(self, inputChannel):
        connected_devices = inputChannel.getConnectedOutputChannels().keys()
        dev = [*connected_devices][0].split(":")[0]
        channel = [self.connections[key]["channel_node"]
                   for key in self.connections.keys() if
                   dev == key][0]
        self.log.INFO("onEndOfStream called")
        self['{}.inFrameRate'.format(channel)] = 0.
        self['{}.outFrameRate'.format(channel)] = 0.
        # Signals end of stream
        self.signalEndOfStream("{}.output".format(channel))
        self.updateState(State.ON)

    def refresh_frame_rate_in(self, channel_idx):
        frame_rate = self.frame_rate_in[channel_idx]
        frame_rate.update()
        fps_in = frame_rate.refresh()
        if fps_in:
            self['chan_{}.inFrameRate'.format(channel_idx)] = fps_in
            self.log.DEBUG("Channel {}: Input rate {} Hz"
                           .format(channel_idx, fps_in))

    def refresh_frame_rate_out(self, channel_idx):
        frame_rate = self.frame_rate_out[channel_idx]
        frame_rate.update()
        fps_out = frame_rate.refresh()
        if fps_out:
            self['chan_{}.outFrameRate'.format(channel_idx)] = fps_out
            self.log.DEBUG("Channel {}: Output rate {} Hz".
                           format(channel_idx, fps_out))

    def on_camera_schema_update(self, deviceId, schema):
        # Look for 'image' in camera's schema
        channel = self.connections[deviceId]["channel_node"]
        path = self.connections[deviceId]["output_image"]
        if schema.has(path):
            sub = schema.subSchema(path)
            shape = sub.getDefaultValue('dims')
            k_type = sub.getDefaultValue('pixels.type')
            self.update_output_schema(channel, shape, k_type)

    @staticmethod
    def create_channel_node(schema, channel, shape=(), k_type=Types.NONE):
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

            # Images should be dropped if processor is too slow
            OVERWRITE_ELEMENT(schema)
            .key(f"{channel}.input.onSlowness")
            .setNewDefaultValue("drop")
            .commit(),

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
        # Get device configuration before schema update
        try:
            outputHostname = self["{}.output.hostname".format(channel)]
        except AttributeError as e:
            # Configuration does not contain "output.hostname"
            outputHostname = None

        newSchema = Schema()
        ImagePatternPicker.create_channel_node(newSchema, channel, shape,
                                               k_type)

        self.updateSchema(newSchema)

        if outputHostname:
            # Restore configuration
            self.log.DEBUG("{}.output.hostname: {}".
                           format(channel, outputHostname))
            self.set("{}.output.hostname".format(channel), outputHostname)
