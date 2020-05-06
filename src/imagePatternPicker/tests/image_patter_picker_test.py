import unittest

from karabo.bound import AlarmCondition, Configurator, Hash, PythonDevice

from ..ImagePatternPicker import ImagePatternPicker


class ImagePatternPicker_TestCase(unittest.TestCase):
    def test_proc(self):
        proc = Configurator(PythonDevice).create("ImagePatternPicker", Hash(
            "Logger.priority", "WARN",
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


if __name__ == '__main__':
    unittest.main()
