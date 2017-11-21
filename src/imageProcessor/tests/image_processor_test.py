import unittest

from karabo.bound import Configurator, Hash, PythonDevice

from ..ImageProcessor import ImageProcessor


class ImageProcessor_TestCase(unittest.TestCase):
    def test_proc(self):
        proc = Configurator(PythonDevice).create("ImageProcessor", Hash(
            "Logger.priority", "DEBUG",
            "deviceId", "ImageProcessor_0"))
        proc.startFsm()


if __name__ == '__main__':
    unittest.main()
