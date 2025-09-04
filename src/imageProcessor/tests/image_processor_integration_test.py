#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on September 3, 2025
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################
import json

import pytest

from karabo.bound import State
from karabo.bound.testing import ServerContext, sleepUntil
from simulatedCameraPy.SimulatedCameraPy import SimulatedCameraPy  # noqa: F401

from ..ImageProcessor import ImageProcessor  # noqa: F401

_CAMERA_ID = "TestCamera"
_PROCESSOR_ID = "TestImageProcessor"
_DEVICE_CONFIG = {
    _CAMERA_ID: {"classId": "SimulatedCameraPy"},
    _PROCESSOR_ID: {
        "classId": "ImageProcessor",
        "input": {
            "connectedOutputChannels": [f"{_CAMERA_ID}:output"]}}
}


@pytest.fixture(scope="module")
def configTest(eventLoop):
    init = json.dumps(_DEVICE_CONFIG)
    server = ServerContext(
        "testServerImageProcessor",
        ["log.level=DEBUG", f"init={init}"])
    with server:
        remote = server.remote()
        sleepUntil(
            lambda: _CAMERA_ID in remote.getDevices() and _PROCESSOR_ID
            in remote.getDevices(), timeout=10)

        yield server


def test_in_sequence(configTest):
    dc = configTest.remote()

    # Idle state
    sleepUntil(lambda: dc.get(_CAMERA_ID, "state") == State.ON, timeout=3)
    sleepUntil(lambda: dc.get(_PROCESSOR_ID, "state") == State.ON, timeout=3)

    # Wait for handshake
    sleepUntil(
        lambda: not dc.get(_PROCESSOR_ID, 'input.missingConnections'),
        timeout=10)

    # Start acquisition
    dc.execute(_CAMERA_ID, "acquire")
    sleepUntil(
        lambda: dc.get(_CAMERA_ID, "state") == State.ACQUIRING, timeout=3)

    # Wait for processor state change
    sleepUntil(
        lambda: dc.get(_PROCESSOR_ID, "state") == State.PROCESSING, timeout=10)

    assert dc.get(_PROCESSOR_ID, "inFrameRate") > 0.0

    # Stop acquisition
    dc.execute(_CAMERA_ID, "stop")
    sleepUntil(
        lambda: dc.get(_CAMERA_ID, "state") == State.ON, timeout=3)

    # Wait for processor state change
    sleepUntil(
        lambda: dc.get(_PROCESSOR_ID, "state") == State.ON, timeout=10)

    assert dc.get(_PROCESSOR_ID, "inFrameRate") == pytest.approx(0.0, abs=0.01)
