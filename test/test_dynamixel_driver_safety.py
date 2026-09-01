"""Startup safety tests for the DYNAMIXEL motor driver."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]


def _load_driver(monkeypatch, events, fail_enable_id=None, fail_reboot_id=None):
    sdk = ModuleType("dynamixel_sdk")
    sdk.COMM_SUCCESS = 0
    sdk.DXL_LOBYTE = lambda value: value & 0xFF
    sdk.DXL_HIBYTE = lambda value: (value >> 8) & 0xFF
    sdk.DXL_LOWORD = lambda value: value & 0xFFFF
    sdk.DXL_HIWORD = lambda value: (value >> 16) & 0xFFFF

    class Port:
        def __init__(self, _device):
            pass

        def openPort(self):
            return True

        def setBaudRate(self, _baudrate):
            return True

        def closePort(self):
            events.append(("close",))

    class Packet:
        def __init__(self, _protocol):
            pass

        def reboot(self, _port, motor_id):
            events.append(("reboot", motor_id))
            return ((-1, 0) if motor_id == fail_reboot_id else (0, 0))

        def write1ByteTxRx(self, _port, motor_id, address, value):
            events.append(("write1", motor_id, address, value))
            if address == 64 and value == 1 and motor_id == fail_enable_id:
                return -1, 0
            return 0, 0

        def write4ByteTxRx(self, _port, motor_id, address, value):
            events.append(("write4", motor_id, address, value))
            return 0, 0

        def read4ByteTxRx(self, _port, motor_id, address):
            events.append(("read4", motor_id, address))
            return 0, 0, 0

    class SyncWrite:
        def __init__(self, *_args):
            pass

        def clearParam(self):
            pass

        def addParam(self, motor_id, _param):
            events.append(("goal", motor_id, 0))
            return True

        def txPacket(self):
            events.append(("goal_tx",))
            return 0

    class BulkRead:
        def __init__(self, *_args):
            pass

    sdk.PortHandler = Port
    sdk.PacketHandler = Packet
    sdk.GroupSyncWrite = SyncWrite
    sdk.GroupBulkRead = BulkRead
    monkeypatch.setitem(sys.modules, "dynamixel_sdk", sdk)
    monkeypatch.syspath_prepend(str(ROOT / "src" / "rosy_bringup"))
    sys.modules.pop("rosy_bringup.dynamixel_driver", None)
    module = importlib.import_module("rosy_bringup.dynamixel_driver")
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    return module.DynamixelDriver("/dev/test", 1_000_000, [1, 2])


def test_initialization_confirms_zero_before_enabling_any_torque(monkeypatch):
    events = []
    driver = _load_driver(monkeypatch, events)

    assert driver.initialize_motors() is True

    zero_tx = events.index(("goal_tx",))
    first_enable = min(
        index
        for index, event in enumerate(events)
        if event[0] == "write1" and event[2:] == (driver.ADDR_TORQUE_ENABLE, 1)
    )
    assert zero_tx < first_enable
    assert ("read4", 1, driver.ADDR_GOAL_VELOCITY) in events
    assert ("read4", 2, driver.ADDR_GOAL_VELOCITY) in events


def test_partial_torque_enable_failure_disables_every_motor(monkeypatch):
    events = []
    driver = _load_driver(monkeypatch, events, fail_enable_id=2)

    assert driver.initialize_motors() is False

    failure_index = events.index(("write1", 2, driver.ADDR_TORQUE_ENABLE, 1))
    cleanup = events[failure_index + 1 :]
    assert ("write1", 1, driver.ADDR_TORQUE_ENABLE, 0) in cleanup
    assert ("write1", 2, driver.ADDR_TORQUE_ENABLE, 0) in cleanup


def test_reboot_failure_stops_initialization_before_torque_enable(monkeypatch):
    events = []
    driver = _load_driver(monkeypatch, events, fail_reboot_id=1)

    assert driver.initialize_motors() is False
    assert not any(
        event[0] == "write1" and event[2:] == (driver.ADDR_TORQUE_ENABLE, 1)
        for event in events
    )
