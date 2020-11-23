import unittest

from karabo.bound import Configurator, Hash, PythonDevice

from ..ImageApplyMask import ImageApplyMask


class ImageMask_TestCase(unittest.TestCase):
    def test_proc(self):
        proc = Configurator(PythonDevice).create("ImageApplyMask", Hash(
            "Logger.priority", "WARN",
            "deviceId", "ImageMask_0"))
        proc.startFsm()


if __name__ == '__main__':
    unittest.main()
