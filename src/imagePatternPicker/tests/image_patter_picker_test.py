import time
import unittest

from karabo.bound import AlarmCondition, Configurator, Hash, PythonDevice

from ..ImagePatternPicker import ImagePatternPicker


class ImagePatternPicker_TestCase(unittest.TestCase):
    def test_proc(self):
        proc = Configurator(PythonDevice).create("ImagePatternPicker", Hash(
            "Logger.priority", "ERROR",
            "deviceId", "ImagePatternPicker_0"))

        proc.startFsm()

        # no warning yet
        self.assertEqual(proc['alarmCondition'], AlarmCondition.NONE)

        # enable cross-hair -> warn
        proc.preReconfigure(Hash('chan_0.enableCrosshair', True))
        self.assertEqual(proc['chan_0.warnCrosshair'], 1)
        self.assertEqual(proc['alarmCondition'], AlarmCondition.WARN)

        # disable cross-hair -> no warn
        proc.preReconfigure(Hash('chan_0.enableCrosshair', False))
        self.assertEqual(proc['chan_0.warnCrosshair'], 0)
        self.assertEqual(proc['alarmCondition'], AlarmCondition.NONE)

        # image trainId == 0 -> warn
        is_valid = proc.is_valid_train_id(0, 'chan_0')
        self.assertEqual(is_valid, False)
        self.assertEqual(proc['chan_0.warnTrainId'], 1)
        self.assertEqual(proc['alarmCondition'], AlarmCondition.WARN)

        # increase trainId -> warn (due to memory effect)
        is_valid = proc.is_valid_train_id(9, 'chan_0')
        self.assertEqual(is_valid, True)  # the trainId in itself is valid
        self.assertEqual(proc['chan_0.warnTrainId'], 1)
        self.assertEqual(proc['alarmCondition'], AlarmCondition.WARN)

        time.sleep(1.)
        # increase trainId -> no warn (no memory after 1 s)
        is_valid = proc.is_valid_train_id(10, 'chan_0')
        self.assertEqual(is_valid, True)
        self.assertEqual(proc['chan_0.warnTrainId'], 0)
        self.assertEqual(proc['alarmCondition'], AlarmCondition.NONE)

        # decrease trainId -> warn
        is_valid = proc.is_valid_train_id(9, 'chan_0')
        self.assertEqual(is_valid, False)
        self.assertEqual(proc['chan_0.warnTrainId'], 1)
        self.assertEqual(proc['alarmCondition'], AlarmCondition.WARN)


if __name__ == '__main__':
    unittest.main()
