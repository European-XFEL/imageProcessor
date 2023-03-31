#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on October 10, 2013
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################

import os.path as op
from random import randint
from time import sleep, time

from karabo.bound import Hash, State
from karabo.integration_tests.utils import BoundDeviceTestCase

RANDIT = randint(0, 1000000)
SERVER_ID = "testServerImageProcessor_{}".format(RANDIT)
PROCESSOR_ID = "testProc_{}".format(RANDIT)
CAMERA_ID = "testCam_{}".format(RANDIT)

SLEEP_TIME = 0.1


class TestImageProcessor(BoundDeviceTestCase):
    def setUp(self):
        super(TestImageProcessor, self).setUp()
        own_dir = op.dirname(op.abspath(__file__))
        # The .egg-info is placed in the parent directory.
        # plugin_dir=egg_dir assures that the pkg_resources plugin loader
        # will identify the test devices as valid plugins with an entry point.
        egg_dir = op.dirname(own_dir)
        class_ids = ['ImageProcessor', 'TestCamera']
        self.start_server('bound', SERVER_ID, class_ids, plugin_dir=egg_dir)
        print(SERVER_ID)

    def test_in_sequence(self):
        config1 = Hash(
            'Logger.priority', 'ERROR',
            'deviceId', PROCESSOR_ID,
            'input.connectedOutputChannels', ['{}:output'.format(CAMERA_ID)]
        )

        class_config1 = Hash('classId', 'ImageProcessor',
                             'deviceId', PROCESSOR_ID,
                             'configuration', config1)

        ok, msg = self.dc.instantiate(SERVER_ID, class_config1, 30)
        self.assertTrue(ok, msg)

        config2 = Hash('Logger.priority', 'ERROR',
                       'deviceId', CAMERA_ID)

        class_config2 = Hash('classId', 'TestCamera',
                             'deviceId', CAMERA_ID,
                             'configuration', config2)

        ok, msg = self.dc.instantiate(SERVER_ID, class_config2, 30)
        self.assertTrue(ok, msg)

        def mergeConf(deviceId, config):
            if deviceId == CAMERA_ID:
                config2.merge(config)
            if deviceId == PROCESSOR_ID:
                config1.merge(config)

        self.dc.registerDeviceMonitor(CAMERA_ID, mergeConf)
        self.dc.registerDeviceMonitor(PROCESSOR_ID, mergeConf)

        # wait for device to init
        state1 = None
        state2 = None
        nTries = 0
        while state1 != State.ON.name or state2 != State.ON.name:
            try:
                state1 = config1['state']
                state2 = config2['state']
            except RuntimeError:
                # A RuntimeError will be raised up to device init.
                # Device initialization can take long, therefore check is
                # done every self._waitTime for maximum self._retries times.
                sleep(self._waitTime)
                if nTries > self._retries:
                    raise TimeoutError("Waiting for device to init timed out")
                nTries += 1

        # tests are run in sequence as sub tests
        # device server thus is only instantiated once
        with self.subTest(msg="Test processor with proper image"):
            self.dc.execute(CAMERA_ID, 'acquire')

            t1 = time()
            while config2['state'] != State.ACQUIRING.name:
                # After camera is initialized, its state should change
                # promptly. Check frequently, for maximum self._waitTime.
                if time() - t1 > self._waitTime:
                    raise TimeoutError("Waiting for camera to acquire timed "
                                       "out")
                sleep(SLEEP_TIME)

            state1 = config1['state']
            fps = config1['inFrameRate']
            t1 = time()
            while state1 != State.ACTIVE.name and not fps > 0.:
                state1 = config1['state']
                fps = config1['inFrameRate']
                if time() - t1 > 1.5:
                    # fps is refreshed every 1 s, thus timeout must be larger.
                    raise TimeoutError("Waiting for processor to be active "
                                       "timed out")
                sleep(SLEEP_TIME)

            self.dc.execute(CAMERA_ID, 'stop')

            state2 = config2['state']
            t1 = time()
            while state2 != State.ON.name:
                state2 = config2['state']
                if time() - t1 > self._waitTime:
                    raise TimeoutError("Waiting for camera to stop timed "
                                       "out")
                sleep(SLEEP_TIME)

            state1 = config1['state']
            fps = config1['inFrameRate']
            t1 = time()
            while state1 != State.ON.name and not fps == 0.:
                state1 = config1['state']
                fps = config1['inFrameRate']
                if time() - t1 > self._waitTime:
                    raise TimeoutError("Waiting for processor to be ON "
                                       "timed out")
                sleep(SLEEP_TIME)
