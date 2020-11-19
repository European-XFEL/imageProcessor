# To change this template, choose Tools | Templates
# and open the template in the editor.

import unittest

from karabo.bound import Configurator, Hash, PythonDevice

from ..SimpleImageProcessor import SimpleImageProcessor


class SimpleImageProcessor_TestCase(unittest.TestCase):
    def test_proc(self):
        proc = Configurator(PythonDevice).create("SimpleImageProcessor", Hash(
            "Logger.priority", "WARN",
            "deviceId", "SimpleImageProcessor_0"))
        proc.startFsm()


if __name__ == '__main__':
    unittest.main()
