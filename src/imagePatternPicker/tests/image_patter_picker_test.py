
import unittest


from karabo.bound import Configurator, Hash, PythonDevice

from ..ImagePatternPicker import ImagePatternPicker


class ImagePatternPicker_TestCase(unittest.TestCase):
    def test_proc(self):
        proc = Configurator(PythonDevice).create("ImagePatternPicker", Hash(
            "Logger.priority", "WARN",
            "deviceId", "ImagePatternPicker_0"))
        proc.startFsm()


if __name__ == '__main__':
    unittest.main()
