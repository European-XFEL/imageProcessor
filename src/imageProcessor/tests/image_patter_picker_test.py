#############################################################################
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################

import time
import unittest

from karabo.bound import AlarmCondition, Configurator, Hash, PythonDevice

from ..ImagePatternPicker import ImagePatternPicker


class ImagePatternPicker_TestCase(unittest.TestCase):
    def test_proc(self):
        proc = Configurator(PythonDevice).create(
            ImagePatternPicker.__name__, Hash(
                "Logger.priority", "ERROR",
                "deviceId", "ImagePatternPicker_0"))

        proc.startFsm()

        # no warning yet
        proc.check_alarm_conditions()
        self.assertEqual(proc['alarmCondition'], AlarmCondition.NONE)

        # enable cross-hair -> warn
        proc['chan_0.enableCrosshair'] = True
        # This will check conditions and update the alarms.
        # On the device the function is called in postReconfigure()
        proc.check_alarm_conditions()
        self.assertEqual(proc['alarmCondition'], AlarmCondition.WARN)

        # disable cross-hair -> no warn
        proc['chan_0.enableCrosshair'] = False
        proc.check_alarm_conditions()
        self.assertEqual(proc['alarmCondition'], AlarmCondition.NONE)

        # image trainId == 0 -> warn
        # is_valid_train_id() will update the alarms by calling
        # check_alarm_conditions()
        is_valid = proc.is_valid_train_id(0, 'chan_0')
        self.assertEqual(is_valid, False)
        self.assertEqual(proc['chan_0.invalidTrainId'], True)
        self.assertEqual(proc['alarmCondition'], AlarmCondition.WARN)

        # increase trainId -> warn (due to memory effect)
        is_valid = proc.is_valid_train_id(9, 'chan_0')
        self.assertEqual(is_valid, True)  # the trainId in itself is valid
        self.assertEqual(proc['chan_0.invalidTrainId'], True)
        self.assertEqual(proc['alarmCondition'], AlarmCondition.WARN)

        time.sleep(1.)
        # increase trainId -> no warn (no memory after 1 s)
        is_valid = proc.is_valid_train_id(10, 'chan_0')
        self.assertEqual(is_valid, True)
        self.assertEqual(proc['chan_0.invalidTrainId'], False)
        self.assertEqual(proc['alarmCondition'], AlarmCondition.NONE)

        # decrease trainId -> warn
        is_valid = proc.is_valid_train_id(9, 'chan_0')
        self.assertEqual(is_valid, False)
        self.assertEqual(proc['chan_0.invalidTrainId'], True)
        self.assertEqual(proc['alarmCondition'], AlarmCondition.WARN)


if __name__ == '__main__':
    unittest.main()
