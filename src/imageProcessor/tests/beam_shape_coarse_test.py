#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on October 10, 2013
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################
import pytest
import pytest_asyncio

from karabo.middlelayer import State, getDevice, sleep
from karabo.middlelayer.testing import AsyncDeviceContext

from ..BeamShapeCoarse import BeamShapeCoarse


@pytest_asyncio.fixture(loop_scope="function")
@pytest.mark.asyncio
async def instantiate_devices():
    conf = {
        "deviceId": "TEST_PROC",
        "input": {}
    }

    dev = BeamShapeCoarse(conf)

    async with AsyncDeviceContext(dev=dev) as ctx:
        yield ctx


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_instantiation(instantiate_devices):
    dev = instantiate_devices["dev"]

    assert dev.state == State.ON


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_warn(instantiate_devices):
    dev = instantiate_devices["dev"]

    # Set error fraction to 0.1
    for _ in range(9):
        dev.errorCounter.update_count()
    dev.errorCounter.update_count(True)

    async with getDevice(dev.deviceId) as proxy:

        # error fraction == threshold == 0.10 -> no warn yet
        assert not proxy.errorCounter.warnCondition

        # lower threshold -> warn
        proxy.errorCounter.threshold = 0.05
        await sleep(0.01)  # need some time to update the warn condition
        assert proxy.errorCounter.warnCondition

        # call 'resetError'
        await proxy.resetError()
        assert not proxy.errorCounter.warnCondition
