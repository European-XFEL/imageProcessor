import unittest

from karabo.bound import Configurator, Hash, PythonDevice

from ..ImageAverager import ImageAverager


class ImageAverages_TestCase(unittest.TestCase):
    def test_proc(self):
        proc = Configurator(PythonDevice).create("ImageAverager", Hash(
            "Logger.priority", "DEBUG",
            "deviceId", "ImageAverages_0"))
        proc.startFsm()


if __name__ == '__main__':
    unittest.main()
