#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on October 10, 2013
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################
import json

import pytest

from karabo.bound import Configurator, Hash, PythonDevice
from karabo.bound.testing import ServerContext, sleepUntil

from ..ImageProcessor import ImageProcessor

_DEVICE_ID = "TestDeviceImageProcessor"
_DEVICE_CONFIG = {
    _DEVICE_ID: {"classId": "ImageProcessor"},
}


@pytest.mark.timeout(30)
def test_device(eventLoop):
    init = json.dumps(_DEVICE_CONFIG)
    server = ServerContext(
        "testServerImageProcessor",
        ["log.level=DEBUG", f"init={init}"])
    with server:
        remote = server.remote()
        sleepUntil(lambda: _DEVICE_ID in remote.getDevices(), timeout=10)


def test_warn():
    proc = Configurator(PythonDevice).create("ImageProcessor", Hash(
        "log.level", "WARN",
        "deviceId", _DEVICE_ID))

    for _ in range(9):
        proc.update_count()
    proc.update_count(True)

    # error fraction == threshold == 0.10 -> no warn yet
    assert not proc['errorCounter.warnCondition']

    # lower threshold -> warn
    proc.preReconfigure(Hash('errorCounter.threshold', 0.05))
    assert proc['errorCounter.warnCondition']

    # call 'resetError'
    proc.resetError()
    assert not proc['errorCounter.warnCondition']


def test_auto_fit_range():
    res = ImageProcessor.auto_fit_range(
        x0=5, y0=5, sx=2, sy=2, sigmas=1, image_width=10, image_height=10)
    assert res == (0, 10, 0, 10)

    res = ImageProcessor.auto_fit_range(
        x0=5, y0=5, sx=2, sy=2, sigmas=1, image_width=10, image_height=10,
        min_range=4)
    assert res == (3, 7, 3, 7)

    res = ImageProcessor.auto_fit_range(
        x0=50, y0=50, sx=2, sy=2, sigmas=1, image_width=100,
        image_height=100)
    assert res == (45, 55, 45, 55)

    res = ImageProcessor.auto_fit_range(
        x0=50, y0=50, sx=5, sy=5, sigmas=3, image_width=100,
        image_height=100)
    assert res == (35, 65, 35, 65)

    res = ImageProcessor.auto_fit_range(
        x0=10, y0=5, sx=2, sy=2, sigmas=3, image_width=20, image_height=10,
        min_range=4)
    assert res == (4, 16, 0, 10)
