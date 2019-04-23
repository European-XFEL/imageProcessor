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
        print("\n\n")
        print("##############################################################")
        print("##############################################################")
        print("##                                                          ##")
        print("##      Starting Exponential running average test case      ##")
        print("##                                                          ##")
        print("##############################################################")
        print("\n\n")

        # Create a dummy camera
        self.testCamera = Configurator(PythonDevice).create("TestCamera", Hash(
            "Logger.priority", "DEBUG",
            "deviceId", "TestCamera_n539"))

    def test_proc(self):
        proc = Configurator(PythonDevice).create("ImageAverager", Hash(
            "Logger.priority", "DEBUG",
            "deviceId", "ImageAverages_1",
            "runningAverage", True,
            "runningAvgMethod", "ExponentialRunningAverage",
            "input.connectedOutputChannels", "TestCamera_n539:output"
        ))
        proc.startFsm()
        # self.testCamera.acquire()
        #
        # time.sleep(5)
        # self.testCamera.stop()


if __name__ == '__main__':
    unittest.main()
