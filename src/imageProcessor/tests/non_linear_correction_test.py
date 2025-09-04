#############################################################################
# Author: <andrea.parenti@xfel.eu>
# Created on September 3, 2025
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################
import pytest
import pytest_asyncio

from karabo.middlelayer import State
from karabo.middlelayer.testing import AsyncDeviceContext

from ..ImageNonLinearCorrection import ImageNonLinearCorrection


@pytest_asyncio.fixture(loop_scope="function")
@pytest.mark.asyncio
async def instantiate_devices():
    conf = {
        "deviceId": "TEST_PROC",
        "input": {}
    }

    dev = ImageNonLinearCorrection(conf)

    async with AsyncDeviceContext(dev=dev) as ctx:
        yield ctx


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_instantiation(instantiate_devices):
    dev = instantiate_devices["dev"]

    assert dev.state == State.ON
