#############################################################################
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################
import json

import pytest

from karabo.bound.testing import ServerContext, sleepUntil

from ..ImagePicker import ImagePicker  # noqa: F401

_DEVICE_ID = "TestDeviceImagePicker"
_DEVICE_CONFIG = {
    _DEVICE_ID: {"classId": "ImagePicker"},
}


@pytest.mark.timeout(30)
def test_device(eventLoop):
    init = json.dumps(_DEVICE_CONFIG)
    server = ServerContext(
        "testServerImagePicker",
        ["log.level=DEBUG", f"init={init}"])
    with server:
        remote = server.remote()
        sleepUntil(lambda: _DEVICE_ID in remote.getDevices(), timeout=10)
