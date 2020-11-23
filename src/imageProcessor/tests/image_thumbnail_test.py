import unittest

from karabo.bound import Configurator, Hash, PythonDevice

from ..ImageThumbnail import ImageThumbnail


class ImageThumbnail_TestCase(unittest.TestCase):
    def test_proc(self):
        proc = Configurator(PythonDevice).create("ImageThumbnail", Hash(
            "Logger.priority", "WARN",
            "deviceId", "ImageThumbnail_0"))
        proc.startFsm()


if __name__ == '__main__':
    unittest.main()
