import unittest

from karabo.bound import Configurator, Hash, PythonDevice

from ..TwoPeakFinder import TwoPeakFinder


class TwoPeakFinder(unittest.TestCase):
    def test_proc(self):
        proc = Configurator(PythonDevice).create("TwoPeakFinder", Hash(
            "Logger.priority", "DEBUG",
            "deviceId", "ImageRoi_0"))
        proc.startFsm()


if __name__ == '__main__':
    unittest.main()
