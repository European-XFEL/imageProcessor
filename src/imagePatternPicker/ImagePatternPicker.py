#############################################################################
# Author: parenti
# Created on April 16, 2019, 02:56 PM
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

from karabo.bound import (
    DaqDataType, DeviceClient, DOUBLE_ELEMENT, INPUT_CHANNEL,
    KARABO_CLASSINFO, IMAGEDATA_ELEMENT, NDARRAY_ELEMENT, NODE_ELEMENT,
    OUTPUT_CHANNEL, OVERWRITE_ELEMENT, PythonDevice, Schema, State, Timestamp,
    Types, UINT32_ELEMENT, UINT64_ELEMENT, Unit
)

from processing_utils.rate_calculator import RateCalculator

NR_OF_CHANNELS = 2


@KARABO_CLASSINFO("ImagePatternPicker", "2.0")
class ImagePatternPicker(PythonDevice):

    @staticmethod
    def expectedParameters(expected):
        data_in = []
        data_out = []

        (
            OVERWRITE_ELEMENT(expected).key('state')
            .setNewOptions(State.ON, State.PROCESSING, State.ERROR)
            .setNewDefaultValue(State.ON)
            .commit()
        )

        for idx in range(NR_OF_CHANNELS):

            data_in.append(Schema())
            data_out.append(Schema())

            (
                NODE_ELEMENT(expected)
                .key('chan_{}'.format(idx))
                .displayedName("Channel {}".format(idx))
                .setDaqDataType(DaqDataType.TRAIN)
                .commit(),

                UINT32_ELEMENT(expected)
                .key("chan_{}.nBunchPatterns".format(idx))
                .displayedName("# Bunch Patterns")
                .description("Number of bunch patterns.")
                .assignmentOptional().defaultValue(2)
                .minInc(1)
                .reconfigurable()
                .commit(),

                UINT32_ELEMENT(expected)
                .key("chan_{}.patternOffset".format(idx))
                .displayedName("Pattern Offset")
                .description("Image will be forwarded to the output if its "
                             "trainId satisfies the following relation: "
                             "(trainId%nBunchPatterns) ==  patternOffset.")
                .assignmentOptional().defaultValue(1)
                .reconfigurable()
                .commit(),

                DOUBLE_ELEMENT(expected)
                .key('chan_{}.inFrameRate'.format(idx))
                .displayedName('Input Frame Rate')
                .description('The input frame rate.')
                .unit(Unit.HERTZ)
                .readOnly()
                .commit(),

                DOUBLE_ELEMENT(expected)
                .key('chan_{}.outFrameRate'.format(idx))
                .displayedName('Output Frame Rate')
                .description('The output frame rate.')
                .unit(Unit.HERTZ)
                .readOnly()
                .commit(),

                NODE_ELEMENT(data_in[-1])
                .key("data")
                .displayedName("Data")
                .setDaqDataType(DaqDataType.TRAIN)
                .commit(),

                IMAGEDATA_ELEMENT(data_in[-1])
                .key("data.image")
                .commit(),

                INPUT_CHANNEL(expected)
                .key("chan_{}.input".format(idx))
                .displayedName("Input")
                .dataSchema(data_in[-1])
                .commit(),

                # Images should be dropped if processor is too slow
                OVERWRITE_ELEMENT(expected)
                .key('chan_{}.input.onSlowness'.format(idx))
                .setNewDefaultValue("drop")
                .commit(),

                NODE_ELEMENT(data_out[-1])
                .key('data')
                .displayedName("Data")
                .commit(),

                IMAGEDATA_ELEMENT(data_out[-1])
                .key('data.image')
                .commit(),

                UINT64_ELEMENT(data_out[-1])
                .key('data.trainId')
                .displayedName('Train ID')
                .readOnly()
                .commit(),

                OUTPUT_CHANNEL(expected)
                .key("chan_{}.output".format(idx))
                .displayedName("Output")
                .dataSchema(data_out[-1])
                .commit(),
            )
        
    def __init__(self, configuration):
        # always call PythonDevice constructor first!
        super(ImagePatternPicker, self).__init__(configuration)

        self.device_client = DeviceClient()

        # Define the first function to be called after the constructor has
        # finished
        self.registerInitialFunction(self.initialization)

    def initialization(self):
        self.frame_rate_in = []
        self.frame_rate_out = []
        self.connections = {}
        for idx in range(NR_OF_CHANNELS):
            chan = "chan_{}".format(idx)
            # Register call-backs
            self.KARABO_ON_DATA("{}.input".format(chan), self.onData)
            self.KARABO_ON_EOS("{}.input".format(chan), self.onEndOfStream)

            # Variables for frames per second computation
            self.frame_rate_in.append(RateCalculator(refresh_interval=1.0))
            self.frame_rate_out.append(RateCalculator(refresh_interval=1.0))

        self.device_client.getDevices()  # Somehow needed to connect
        for idx in range(NR_OF_CHANNELS):
            chan = "chan_{}".format(idx)
            input_chan = '{}.input.connectedOutputChannels'.format(chan)
            output_image = '{}.output.schema.data.image'.format(chan)
            try:
                inputs = self[input_chan]
                if inputs:
                    connected_chan = inputs[0]
                    device_id = connected_chan.split(":")[0]
                    self.connections[device_id] = {}
                    connected_pipe = connected_chan.split(":")[1]
                    self.connections[device_id]["in_pipeline"] = connected_pipe
                    self.connections[device_id]["out_image"] = output_image
                    if device_id:
                        print(self.connections)
                        self.device_client.registerSchemaUpdatedMonitor(
                            self.on_camera_schema_update)
#                        self.device_client.getDeviceSchemaNoWait(device_id)
            except Exception as e:
                print(e)
            #(KeyError, RuntimeError):
            #    pass

    def onData(self, data, metaData):
        if self['state'] == State.ON:
            self.log.INFO("Start of Stream")
            self.updateState(State.PROCESSING)

        self.refresh_frame_rate_in()

        ts = Timestamp.fromHashAttributes(
            metaData.getAttributes('timestamp'))
        train_id = ts.getTrainId()
        if (train_id % self['nBunchPatterns']) == self['patternOffset']:
            data['data.trainId'] = train_id
            self.writeChannel('output', data, ts)
            self.refresh_frame_rate_out()

    def onEndOfStream(self, inputChannel):
        self.log.INFO("onEndOfStream called")
        self['inFrameRate'] = 0.
        self['outFrameRate'] = 0.
        # Signals end of stream
        self.signalEndOfStream("output")
        self.updateState(State.ON)

    def refresh_frame_rate_in(self):
        self.frame_rate_in.update()
        fps_in = self.frame_rate_in.refresh()
        if fps_in:
            self['inFrameRate'] = fps_in
            self.log.DEBUG("Input rate {} Hz".format(fps_in))

    def refresh_frame_rate_out(self):
        self.frame_rate_out.update()
        fps_out = self.frame_rate_out.refresh()
        if fps_out:
            self['outFrameRate'] = fps_out
            self.log.DEBUG("Output rate {} Hz".format(fps_out))

    def on_camera_schema_update(self, deviceId, schema):
        print("SCHEMA; ", schema, deviceId, self.connestions)
        """
        # Look for 'image' in camera's schema
        output = self.connestions[deviceId]["in_pipeline"]
        path = self.connestions[deviceId]["out_image"]
        print(output, path)
        path = f'{output}.schema.data.image'
        if schema.has(path):
            sub = schema.subSchema(path)
            shape = sub.getDefaultValue('dims')
            k_type = sub.getDefaultValue('pixels.type')
            print(sub, shape, k_type)
            self.update_output_schema(shape, k_type)
        """
    def update_output_schema(self, shape, k_type):
        """
        # Get device configuration before schema update
        try:
            outputHostname = self["output.hostname"]
        except AttributeError as e:
            # Configuration does not contain "output.hostname"
            outputHostname = None

        newSchema = Schema()
        dataSchema = Schema()
        (
            NODE_ELEMENT(dataSchema).key("data")
            .displayedName("Data")
            .setDaqDataType(DaqDataType.TRAIN)
            .commit(),

            IMAGEDATA_ELEMENT(dataSchema).key("data.image")
            .displayedName("Image")
            .setDimensions(str(shape).strip("()"))
            .commit(),

            # Set (overwrite) shape and dtype for internal NDArray element -
            # needed by DAQ
            NDARRAY_ELEMENT(dataSchema).key("data.image.pixels")
            .shape(list(shape))
            .dtype(Types.values[k_type])
            .commit(),

            # Set "maxSize" for vector properties - needed by DAQ
            dataSchema.setMaxSize("data.image.dims", len(shape)),
            dataSchema.setMaxSize("data.image.dimTypes", len(shape)),
            dataSchema.setMaxSize("data.image.roiOffsets", len(shape)),
            dataSchema.setMaxSize("data.image.binning", len(shape)),
            dataSchema.setMaxSize("data.image.pixels.shape", len(shape)),

            OUTPUT_CHANNEL(newSchema).key("output")
            .displayedName("Output")
            .dataSchema(dataSchema)
            .commit(),
        )
        self.updateSchema(newSchema)
        if outputHostname:
            # Restore configuration
            self.log.DEBUG(f"output.hostname: {outputHostname}")
            self.set("output.hostname", outputHostname)
        """
