import unittest
import time
from karabo.bound import Configurator, Hash, PythonDevice

from ..ImageAverager import ImageAverager


class ImageAverages_TestCase(unittest.TestCase):
    def test_proc(self):
        proc = Configurator(PythonDevice).create("ImageAverager", Hash(
            "Logger.priority", "DEBUG",
            "deviceId", "ImageAverages_0"))
        proc.startFsm()


class ImageAverage_ExpAverage_TestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_instantiation(self):
        self.imavg = Configurator(PythonDevice).create("ImageAverager", Hash(
            "Logger.priority", "DEBUG",
            "deviceId", "ImageAverages_1",
            "runningAverage", True,
            "runningAvgMethod", "ExponentialRunningAverage"
        ))
        self.imavg.startFsm()

        self.imavg.log.INFO("Instantiated ImageAverager instance in "
                            "exponential running average mode.")
        time.sleep(1)
        self.imavg.log.INFO("\n###########################################")
        self.imavg.log.INFO("##       Averager Instantiated           ##")
        self.imavg.log.INFO("###########################################\n")


if __name__ == '__main__':
    unittest.main()
