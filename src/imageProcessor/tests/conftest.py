# This file is intended to be used together with Karabo:
#
# http://www.karabo.eu
#
# IF YOU REQUIRE ANY LICENSING AND COPYRIGHT TERMS, PLEASE ADD THEM HERE.
# Karabo itself is licensed under the terms of the MPL 2.0 license.
import pytest

from karabo.bound.testing import eventLoop  # noqa: F401
from karabo.middlelayer.testing import KaraboTestLoopPolicy


@pytest.fixture()
def event_loop_policy():
    return KaraboTestLoopPolicy()
