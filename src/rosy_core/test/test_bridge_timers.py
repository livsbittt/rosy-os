"""Structural harness: what `RosBridge.__init__` registers on the node.

**Read this before extending it.** The plan that produced this file rejected a
stubbed-rclpy harness as a *strategy*, for four reasons that have not gone away:
tests against a stub assert stub semantics; QoS, `MultiThreadedExecutor`
re-entrancy, timer scheduling and action futures are exactly what makes the
bridge risky and exactly what a stub erases; it forks an unvalidated rclpy
surface in-tree; and its maintenance cost grows with every message type.

It survived as **one concession**: a stub is the only credible way to make the
3b adapter reshape gradable without a robot, because it can assert that
`__init__` still registers the same timers at the same periods. Structural, not
semantic. That is the whole mandate.

So:

- **Do not** add a test here that calls a callback, drives a tick, or asserts on
  a message value. Those belong in the ROS-free siblings (`translate.py`,
  `display.py`, `reconcile.py`, `odometry.py`, `save_map.py`,
  `battery_policy.py`, `goal_tracker.py`), where no stub is involved.
- **Do not** move the stub into `conftest.py`. It lives in this file so its
  blast radius is this file: nothing else can start depending on stub
  semantics by accident.
- The periods below are the contract. `1/50` is D-2, the sole `cmd_vel`
  publisher, and a reshape that changes it is the failure this exists to catch.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import pytest
import yaml

CONFIG_DIR = Path(__file__).parent.parent / "config"

#: The ROS modules `ros_bridge` imports. Each is replaced by a module whose every
#: attribute is a distinct dummy class — enough for `create_publisher(Twist, ...)`
#: to resolve `Twist`, because `__init__` only ever passes these as type
#: arguments and never constructs one.
_ROS_MODULES = [
    "rclpy", "rclpy.action", "rclpy.node", "rclpy.qos",
    "geometry_msgs", "geometry_msgs.msg",
    "nav_msgs", "nav_msgs.msg",
    "nav2_msgs", "nav2_msgs.action", "nav2_msgs.msg",
    "sensor_msgs", "sensor_msgs.msg",
    "std_msgs", "std_msgs.msg",
    "std_srvs", "std_srvs.srv",
    "rosy_interfaces", "rosy_interfaces.srv",
    "tf2_ros",
]


class _Permissive(type):
    """Metaclass so `ReliabilityPolicy.RELIABLE` and friends resolve to something."""

    def __getattr__(cls, name: str) -> Any:
        created = _Permissive(name, (), {})
        setattr(cls, name, created)
        return created


class _Anything(types.ModuleType):
    """A module that answers any attribute with a fresh permissive dummy class."""

    def __getattr__(self, name: str) -> Any:
        created = _Permissive(name, (), {"__init__": lambda self, *a, **k: None})
        setattr(self, name, created)
        return created


class RecordingNode:
    """Records what the bridge registers. Executes nothing."""

    def __init__(self) -> None:
        self.timers: list[float] = []
        self.subscriptions: list[str] = []
        self.publishers: list[str] = []
        self.clients: list[str] = []

    def create_timer(self, period_s, _callback):
        self.timers.append(period_s)
        return object()

    def create_subscription(self, _type, topic, _callback, _qos):
        self.subscriptions.append(topic)
        return object()

    def create_publisher(self, _type, topic, _qos):
        self.publishers.append(topic)
        return object()

    def create_client(self, _type, name):
        self.clients.append(name)
        return types.SimpleNamespace(service_is_ready=lambda: False)

    def get_logger(self):
        return types.SimpleNamespace(
            info=lambda *a, **k: None, warn=lambda *a, **k: None,
            warning=lambda *a, **k: None, error=lambda *a, **k: None,
            debug=lambda *a, **k: None)

    def get_clock(self):
        return types.SimpleNamespace(
            now=lambda: types.SimpleNamespace(to_msg=lambda: None))


@pytest.fixture
def registered(tmp_path, monkeypatch):
    """Build a `RosBridge` against stubbed ROS and return the recording node."""
    from rosy_core.profile import RobotProfile
    from rosy_core.services import CoreServices

    for name in _ROS_MODULES:
        monkeypatch.setitem(sys.modules, name, _Anything(name))
    monkeypatch.delitem(sys.modules, "rosy_core.bridge.ros_bridge", raising=False)

    def read(name):
        return yaml.safe_load((CONFIG_DIR / name).read_text(encoding="utf-8"))

    config = read("rosy_default.yaml")
    services = CoreServices.build(
        config, RobotProfile.load(CONFIG_DIR / "profile.pinky_pro.yaml"),
        read("capabilities.yaml"), tmp_path / "wp.json")

    from rosy_core.bridge.ros_bridge import RosBridge

    node = RecordingNode()
    RosBridge(node, services)
    return node


#: Period in seconds, in registration order. `1/50` is D-2's sole `cmd_vel`
#: publisher; `1/10` is the state snapshot rate from `rosy_default.yaml`.
EXPECTED_TIMERS = [1.0 / 50.0, 1.0 / 10.0, 1.0, 1.0 / 5.0, 1.0 / 5.0, 1.0 / 5.0]


def test_the_bridge_registers_six_timers_at_the_expected_periods(registered):
    """The one thing this harness exists to hold across the 3b reshape.

    Moving the timers into per-domain adapters must not change how many there
    are, how fast they run, or the order they are created in. A dropped timer is
    a subsystem that silently stops ticking; a changed period on the first one
    is the D-2 cmd_vel contract.
    """
    assert registered.timers == EXPECTED_TIMERS


def test_the_cmd_vel_timer_is_first_and_fifty_hertz(registered):
    """D-2 called out on its own, because it is the one with a safety argument."""
    assert registered.timers[0] == pytest.approx(0.02)


#: Every topic, publisher and service the bridge wires at construction. Same
#: mandate as the timers: 3b moves these into per-domain adapters, and a
#: subscription that quietly fails to move is a sensor the robot stops hearing.
EXPECTED_SUBSCRIPTIONS = [
    "odom", "battery/voltage", "nav_cmd_vel", "scan", "imu_raw",
    "us_sensor/range", "batt_state", "map", "plan",
    "local_costmap/costmap_raw", "global_costmap/costmap_raw",
]
EXPECTED_PUBLISHERS = [
    "cmd_vel", "initialpose", "power/mode", "display/info",
    "docking/collision_exemption",
]
EXPECTED_CLIENTS = ["set_led", "start_motor", "stop_motor"]


def test_the_bridge_subscribes_to_the_same_topics(registered):
    assert registered.subscriptions == EXPECTED_SUBSCRIPTIONS


def test_the_bridge_advertises_the_same_publishers(registered):
    """`cmd_vel` first and once: D-2 says there is exactly one publisher."""
    assert registered.publishers == EXPECTED_PUBLISHERS
    assert registered.publishers.count("cmd_vel") == 1


def test_the_bridge_opens_the_same_service_clients(registered):
    assert registered.clients == EXPECTED_CLIENTS
