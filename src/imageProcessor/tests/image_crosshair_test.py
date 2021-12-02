import unittest

from karabo.bound import Configurator, Hash, PythonDevice

from ..ImageCrosshair import ImageCrosshair


class ImageCrosshair_TestCase(unittest.TestCase):
    def test_proc(self):
        proc = Configurator(PythonDevice).create("ImageCrosshair", Hash(
            "Logger.priority", "WARN",
            "deviceId", "ImageCrosshair_0"))
        proc.startFsm()


if __name__ == '__main__':
    unittest.main()
