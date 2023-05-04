#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on May  3, 2023
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################

import unittest

from karabo.bound import Configurator, Hash, PythonDevice

from ..SimpleImageProcessor import SimpleImageProcessor


class SimpleImageProcessor_TestCase(unittest.TestCase):
    def test_simple_image_processor(self):
        proc = Configurator(PythonDevice).create("SimpleImageProcessor", Hash(
            "Logger.priority", "WARN",
            "deviceId", "SimpleImageProcessor_0"))
        proc.startFsm()


if __name__ == '__main__':
    unittest.main()
