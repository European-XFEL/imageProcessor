import unittest

from karabo.bound import Configurator, Hash, PythonDevice

from ..AutoCorrelator import AutoCorrelator


class AutoCorrelator_TestCase(unittest.TestCase):
    def test_autocorrelator(self):
        autocorrelator = Configurator(PythonDevice).create(
            "AutoCorrelator", Hash(
                "Logger.priority", "WARN", "deviceId", "AutoCorrelator_0"
            )
        )
        autocorrelator.startFsm()


if __name__ == '__main__':
    unittest.main()
