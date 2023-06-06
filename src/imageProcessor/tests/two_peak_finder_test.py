#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on October 10, 2013
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################

import unittest

import numpy as np

from image_processing.image_processing import gauss1d
from karabo.bound import Configurator, Hash, PythonDevice

from ..TwoPeakFinder import TwoPeakFinder, find_peaks


class TwoPeakFinder_TestCase(unittest.TestCase):
    def test_proc(self):
        proc = Configurator(PythonDevice).create("TwoPeakFinder", Hash(
            "Logger.priority", "WARN",
            "deviceId", "ImageRoi_0"))
        proc.startFsm()

    def test_finding(self):
        x = np.arange(2048)
        img_x = gauss1d(x, 1000, 300, 20) + gauss1d(x, 800, 600, 25)
        img_x = img_x.astype(np.uint16)
        zero_point = 450
        peaks = find_peaks(img_x, zero_point)
        self.assertAlmostEqual(peaks[0], 1000, delta=1)  # value 1
        self.assertAlmostEqual(peaks[1], 300, delta=1)  # position 1
        self.assertAlmostEqual(peaks[2], 47, delta=1)  # FWHM 1 = 2.35*sigma_1
        self.assertAlmostEqual(peaks[3], 800, delta=1)  # value 2
        self.assertAlmostEqual(peaks[4], 600, delta=1)  # position 2
        self.assertAlmostEqual(peaks[5], 59, delta=1)  # FWHM 2


if __name__ == '__main__':
    unittest.main()
