#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on October 10, 2013
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################

from contextlib import contextmanager
from uuid import uuid4

from imageProcessor.BeamShapeCoarse import BeamShapeCoarse
from karabo.middlelayer import AlarmCondition, getDevice, sleep
from karabo.middlelayer.testing import DeviceTest, async_tst

device_id = f"TestProc{uuid4()}"
conf = {
    'classId': 'BeamShapeCoarse',
    '_deviceId_': device_id,
    'input': {}
}


class BeamShapeTestCase(DeviceTest):
    @classmethod
    @contextmanager
    def lifetimeManager(cls):
        cls.dev = BeamShapeCoarse(conf)

        with cls.deviceManager(cls.dev, lead=cls.dev):
            yield

    @async_tst
    async def test_warn(self):
        with (await getDevice(device_id)) as proc:
            for _ in range(9):
                self.dev.errorCounter.update_count()
            self.dev.errorCounter.update_count(True)

            # error fraction == threshold == 0.10 -> no warn yet
            self.assertEqual(self.dev.errorCounter.warnCondition, 0)
            self.assertEqual(self.dev.alarmCondition, AlarmCondition.NONE)

            # lower threshold -> warn
            proc.errorCounter.threshold = 0.05  # call setter function
            await sleep(0.01)  # wait for setter function
            self.assertEqual(self.dev.errorCounter.warnCondition, 1)
            self.assertEqual(self.dev.alarmCondition, AlarmCondition.WARN)

            # call 'resetError'
            await self.dev.resetError()
            self.assertEqual(self.dev.errorCounter.warnCondition, 0)
            self.assertEqual(self.dev.alarmCondition, AlarmCondition.NONE)
