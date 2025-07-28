#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on October 10, 2013
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################
import json
from math import isclose

import numpy as np
import pytest

from image_processing.image_processing import gauss1d
from karabo.bound.testing import ServerContext, sleepUntil

from ..TwoPeakFinder import TwoPeakFinder, find_peaks  # noqa: F401

_DEVICE_ID = "TestDeviceTwoPeakFinder"
_DEVICE_CONFIG = {
    _DEVICE_ID: {"classId": "TwoPeakFinder"},
}


@pytest.mark.timeout(30)
def test_device(eventLoop):
    init = json.dumps(_DEVICE_CONFIG)
    server = ServerContext(
        "testServerTwoPeakFinder",
        ["log.level=DEBUG", f"init={init}"])
    with server:
        remote = server.remote()
        sleepUntil(lambda: _DEVICE_ID in remote.getDevices(), timeout=10)


def test_finding():
    x = np.arange(2048)
    img_x = gauss1d(x, 1000, 300, 20) + gauss1d(x, 800, 600, 25)
    img_x = img_x.astype(np.uint16)
    zero_point = 450
    peaks = find_peaks(img_x, zero_point)
    assert isclose(peaks[0], 1000, abs_tol=1)  # value 1
    assert isclose(peaks[1], 300, abs_tol=1)  # position 1
    assert isclose(peaks[2], 47, abs_tol=1)  # FWHM 1 = 2.35*sigma_1
    assert isclose(peaks[3], 800, abs_tol=1)  # value 2
    assert isclose(peaks[4], 600, abs_tol=1)  # position 2
    assert isclose(peaks[5], 59, abs_tol=1)  # FWHM 2
