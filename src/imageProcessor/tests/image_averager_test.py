import unittest
import time
from karabo.bound import Configurator, Hash, PythonDevice

from ..ImageAverager import ImageAverager
from .test_camera import TestCamera


class ImageAverages_TestCase(unittest.TestCase):
    def test_proc(self):
        proc = Configurator(PythonDevice).create("ImageAverager", Hash(
            "Logger.priority", "DEBUG",
            "deviceId", "ImageAverages_0"))
        proc.startFsm()


class ImageAverage_ExpAverage_TestCase(unittest.TestCase):
    def setUp(self):

        # Create a dummy camera
        self.testCamera = Configurator(PythonDevice).create("TestCamera", Hash(
            "Logger.priority", "DEBUG",
            "deviceId", "TestCamera_n539"))

        self.testCamera.log.INFO("Instantiated TestCamera instance")
        time.sleep(10)

        self.testCamera.log.INFO("\n\n")
        self.testCamera.log.INFO("###########################################")
        self.testCamera.log.INFO("###########################################")
        self.testCamera.log.INFO("##                                       ##")
        self.testCamera.log.INFO("## Exponential running average test case ##")
        self.testCamera.log.INFO("##                                       ##")
        self.testCamera.log.INFO("###########################################")
        self.testCamera.log.INFO("\n\n")



    def tearDown(self):
        pass

    def test_instantiation(self):
        proc = Configurator(PythonDevice).create("ImageAverager", Hash(
            "Logger.priority", "DEBUG",
            "deviceId", "ImageAverages_1",
            "runningAverage", True,
            "runningAvgMethod", "ExponentialRunningAverage",
            "input.connectedOutputChannels", ["TestCamera_n539:output"]
        ))
        proc.startFsm()
        proc.log.INFO("Instantiated ImageAverager instance in "
                      "exponential running average mode.")

        self.testCamera.log.INFO("Starting acquisition with TestCamera.")
        self.testCamera.acquire()

        time.sleep(5)
        # self.testCamera.stop()


if __name__ == '__main__':
    unittest.main()
