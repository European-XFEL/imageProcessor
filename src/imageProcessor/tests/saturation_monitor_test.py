#############################################################################
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################
import json

import pytest

from karabo.bound.testing import ServerContext, sleepUntil

from ..SaturationMonitor import SaturationMonitor  # noqa: F401

_DEVICE_ID = "TestDeviceSaturationMonitor"
_DEVICE_CONFIG = {
    _DEVICE_ID: {
        "classId": "SaturationMonitor",
        "alarmThreshold": 1000.0,
        "warnThreshold": 800.0,
        "alarmMaxCount": 1,
        "warnMaxCount": 10},
}


@pytest.mark.timeout(30)
def test_device(eventLoop):
    init = json.dumps(_DEVICE_CONFIG)
    server = ServerContext(
        "testServerSaturationMonitor",
        ["log.level=DEBUG", f"init={init}"])
    with server:
        remote = server.remote()
        sleepUntil(lambda: _DEVICE_ID in remote.getDevices(), timeout=10)
