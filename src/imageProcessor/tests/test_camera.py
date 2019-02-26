#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on October 23, 2018
# Copyright (C) European XFEL GmbH Hamburg. All rights reserved.
#############################################################################

import numpy as np

from karabo.bound import (
    BOOL_ELEMENT, Hash, ImageData, IMAGEDATA_ELEMENT, KARABO_CLASSINFO,
    NODE_ELEMENT, OUTPUT_CHANNEL, OVERWRITE_ELEMENT, PythonDevice,
    Schema, SLOT_ELEMENT, State, Worker
)


@KARABO_CLASSINFO("TestCamera", "2.2")
class TestCamera(PythonDevice):
    TIMEOUT = 0.1  # interval between images

    def __init__(self, configuration):
        # always call PythonDevice constructor first!
        super(TestCamera, self).__init__(configuration)

        gauss_x = np.exp(-(np.arange(1024)-400)**2/1000)
        gauss_y = np.exp(-(np.arange(2048)-600)**2/1600)
        nd_array = (1000*np.outer(gauss_y, gauss_x)).astype('uint16')
        image_data = ImageData(nd_array)
        self._image_ok = Hash("data.image", image_data)
        self._image_nok = Hash("data.image", 0.)

        self._write_worker = None

        self.registerInitialFunction(self.initialize)

        self.KARABO_SLOT(self.acquire)
        self.KARABO_SLOT(self.stop)

    @staticmethod
    def expectedParameters(expected):
        outputData = Schema()
        (
            OVERWRITE_ELEMENT(expected).key("state")
                .setNewOptions(State.ON, State.ACQUIRING)
                .setNewDefaultValue(State.ON)
                .commit(),

            NODE_ELEMENT(outputData).key("data")
                .displayedName("Data")
                .commit(),

            IMAGEDATA_ELEMENT(outputData).key("data.image")
                .displayedName("Image")
                .commit(),

            OUTPUT_CHANNEL(expected).key("output")
                .displayedName("Output")
                .dataSchema(outputData)
                .commit(),

            BOOL_ELEMENT(expected).key("corruptedImage")
                .displayedName("Corrupted Image")
                .description("If True, some invalid image will be written to "
                             "the output channel.")
                .assignmentOptional().defaultValue(False)
                .reconfigurable()
                .commit(),

            SLOT_ELEMENT(expected).key("acquire")
                .displayedName("Acquire")
                .description("Instructs camera to go into acquisition state")
                .allowedStates(State.ON)
                .commit(),

            SLOT_ELEMENT(expected).key("stop")
                .displayedName("Stop")
                .description("Instructs camera to stop current acquisition")
                .allowedStates(State.ACQUIRING)
                .commit(),

        )

    def initialize(self):
        """Initial function"""
        if self._write_worker is None:
            self._write_worker = Worker(self._write_to_channel,
                                        self.TIMEOUT, -1)
            self._write_worker.daemon = True

    def acquire(self):
        """Start sending images"""
        self._write_worker.start()
        self.updateState(State.ACQUIRING)

    def stop(self):
        """Stop sending images"""
        self._write_worker.pause()
        self.signalEndOfStream("output")
        self.updateState(State.ON)

    def _write_to_channel(self):
        if not self['corruptedImage']:
            self.writeChannel("output", self._image_ok)
        else:
            self.writeChannel("output", self._image_nok)
