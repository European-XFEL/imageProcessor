#############################################################################
# Copyright (C) European XFEL GmbH Schenefeld. All rights reserved.
#############################################################################
import json
from time import sleep

import pytest

from karabo.bound import AlarmCondition, Configurator, Hash, PythonDevice
from karabo.bound.testing import ServerContext, sleepUntil

from ..ImagePatternPicker import ImagePatternPicker

_DEVICE_ID = "TestDeviceImagePatternPicker"
_DEVICE_CONFIG = {
    _DEVICE_ID: {"classId": "ImagePatternPicker"},
}


@pytest.mark.timeout(30)
def test_device(eventLoop):
    init = json.dumps(_DEVICE_CONFIG)
    server = ServerContext(
        "testServerImagePatternPicker",
        ["log.level=DEBUG", f"init={init}"])
    with server:
        remote = server.remote()
        sleepUntil(lambda: _DEVICE_ID in remote.getDevices(), timeout=10)


def test_alarm():
    proc = Configurator(PythonDevice).create(
        ImagePatternPicker.__name__, Hash(
            "log.level", "ERROR",
            "deviceId", "ImagePatternPicker_0"))

    # no warning yet
    proc.check_alarm_conditions()
    assert proc['alarmCondition'] == AlarmCondition.NONE

    # enable cross-hair -> warn
    proc['chan_0.enableCrosshair'] = True
    # This will check conditions and update the alarms.
    # On the device the function is called in postReconfigure()
    proc.check_alarm_conditions()
    assert proc['alarmCondition'] == AlarmCondition.WARN

    # disable cross-hair -> no warn
    proc['chan_0.enableCrosshair'] = False
    proc.check_alarm_conditions()
    assert proc['alarmCondition'] == AlarmCondition.NONE

    # image trainId == 0 -> warn
    # is_valid_train_id() will update the alarms by calling
    # check_alarm_conditions()
    is_valid = proc.is_valid_train_id(0, 'chan_0')
    assert not is_valid
    assert proc['chan_0.invalidTrainId']
    assert proc['alarmCondition'] == AlarmCondition.WARN

    # increase trainId -> warn (due to memory effect)
    is_valid = proc.is_valid_train_id(9, 'chan_0')
    assert is_valid  # the trainId in itself is valid
    assert proc['chan_0.invalidTrainId']
    assert proc['alarmCondition'] == AlarmCondition.WARN

    sleep(1.)
    # increase trainId -> no warn (no memory after 1 s)
    is_valid = proc.is_valid_train_id(10, 'chan_0')
    assert is_valid
    assert not proc['chan_0.invalidTrainId']
    assert proc['alarmCondition'] == AlarmCondition.NONE

    # decrease trainId -> warn
    is_valid = proc.is_valid_train_id(9, 'chan_0')
    assert not is_valid
    assert proc['chan_0.invalidTrainId']
    assert proc['alarmCondition'] == AlarmCondition.WARN
