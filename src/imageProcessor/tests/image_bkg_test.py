#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on October 10, 2013
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################

import unittest

from karabo.bound import Configurator, Hash, PythonDevice

from ..ImageBackgroundSubtraction import ImageBackgroundSubtraction


class ImageBackgroundSubtraction_TestCase(unittest.TestCase):
    def test_proc(self):
        proc = Configurator(PythonDevice).create(
            "ImageBackgroundSubtraction",
            Hash("Logger.priority", "WARN", "deviceId",
                 "ImageBackgroundSubtraction_0"))
        proc.startFsm()


if __name__ == '__main__':
    unittest.main()
