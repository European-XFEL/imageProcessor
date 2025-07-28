#############################################################################
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################
import json

import pytest

from karabo.bound.testing import ServerContext, sleepUntil

from ..AutoCorrelator import AutoCorrelator  # noqa: F401

_DEVICE_ID = "TestDeviceAutoCorrelator"
_DEVICE_CONFIG = {
    _DEVICE_ID: {"classId": "AutoCorrelator"},
}


@pytest.mark.timeout(30)
def test_device(eventLoop):
    init = json.dumps(_DEVICE_CONFIG)
    server = ServerContext(
        "testServerAutoCorrelator",
        ["log.level=DEBUG", f"init={init}"])
    with server:
        remote = server.remote()
        sleepUntil(lambda: _DEVICE_ID in remote.getDevices(), timeout=10)
