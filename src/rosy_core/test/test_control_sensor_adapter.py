"""Contract tests for the optional Rosy Control sensor-only adapter."""

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from rosy_core.bridge.control_sensor_adapter import (
    ControlSensorAdapter,
    ControlSensorConfig,
)


class FakeSensorNode:
    def __init__(self, revision="sensor-revision", **kwargs):
        self.profile = SimpleNamespace(revision=revision)
        self.pub = None
        self.raw_zero_pub = None
        self.estop_pub = None
        self.decision_pub = None
        self.bind_calls = []
        self.destroyed = False
        self.factory_kwargs = kwargs

    def bind_policy_handoff(self, policy, required, applied_revision=None):
        self.bind_calls.append((policy, tuple(required), applied_revision))
        return applied_revision

    def destroy_node(self):
        self.destroyed = True


def test_default_configuration_is_disabled_and_has_no_sensor_node():
    calls = []

    adapter = ControlSensorAdapter(sensor_node_factory=lambda **kwargs: calls.append(kwargs))

    assert adapter.enabled is False
    assert adapter.node is None
    assert adapter.policy is None
    assert adapter.attach(object()) is False
    assert calls == []


def test_enabled_configuration_constructs_sensor_only_node_and_binds_applied_revision():
    created = []

    def factory(**kwargs):
        sensor = FakeSensorNode(**kwargs)
        created.append(sensor)
        return sensor

    adapter = ControlSensorAdapter(
        {
            "enabled": True,
            "required": ["lidar", "imu", "ir"],
            "max_age": 0.4,
            "parameters": {"sensor_timeout": 0.8},
        },
        sensor_node_factory=factory,
    )

    assert adapter.enabled is True
    assert adapter.policy is not None
    assert adapter.policy.revision == "sensor-revision"
    assert len(created) == 1
    assert created[0].factory_kwargs == {
        "parameter_overrides": {"sensor_timeout": 0.8},
        "sensor_only": True,
    }
    assert len(created[0].bind_calls) == 1
    policy, required, revision = created[0].bind_calls[0]
    assert policy is adapter.policy
    assert required == ("lidar", "imu", "ir")
    assert revision == "sensor-revision"


def test_namespaced_worker_receives_the_core_namespace():
    received = []

    def factory(**kwargs):
        received.append(kwargs)
        return FakeSensorNode(**kwargs)

    ControlSensorAdapter({"enabled": True}, sensor_node_factory=factory,
                         namespace="/rosy_01")

    assert received == [{
        "parameter_overrides": {},
        "sensor_only": True,
        "namespace": "/rosy_01",
    }]


def test_adapter_can_bind_the_same_policy_to_core_safety_manager():
    sensor = FakeSensorNode()
    adapter = ControlSensorAdapter(
        {"enabled": True}, sensor_node_factory=lambda **kwargs: sensor
    )

    class Safety:
        def __init__(self):
            self.bound = None

        def bind_control_policy(self, policy):
            self.bound = policy

    safety = Safety()
    assert adapter.bind_safety(safety) is True
    assert safety.bound is adapter.policy


def test_adapter_refuses_a_sensor_node_with_any_command_authority():
    def factory(**kwargs):
        node = FakeSensorNode(**kwargs)
        node.pub = object()
        return node

    with pytest.raises(ValueError, match="command authority"):
        ControlSensorAdapter({"enabled": True}, sensor_node_factory=factory)


def test_adapter_attach_and_close_are_idempotent():
    sensor = FakeSensorNode()
    adapter = ControlSensorAdapter(
        {"enabled": True}, sensor_node_factory=lambda **kwargs: sensor
    )

    class Executor:
        def __init__(self):
            self.added = []
            self.removed = []

        def add_node(self, node):
            self.added.append(node)

        def remove_node(self, node):
            self.removed.append(node)

    executor = Executor()
    assert adapter.attach(executor) is True
    assert adapter.attach(executor) is False
    assert adapter.detach(executor) is True
    assert adapter.detach(executor) is False
    assert adapter.close() is True
    assert adapter.close() is False
    assert executor.added == [sensor]
    assert executor.removed == [sensor]
    assert sensor.destroyed is True


def test_core_node_owns_adapter_before_bridge_and_closes_it_with_executor():
    path = Path(__file__).parents[1] / "rosy_core" / "node.py"
    module = ast.parse(path.read_text(encoding="utf-8"))
    cls = next(node for node in module.body
               if isinstance(node, ast.ClassDef) and node.name == "RosyCoreNode")
    methods = {
        node.name: node for node in cls.body
        if isinstance(node, ast.FunctionDef)
    }
    init_source = ast.get_source_segment(path.read_text(encoding="utf-8"), methods["__init__"])
    run_source = ast.get_source_segment(path.read_text(encoding="utf-8"), methods["run"])
    shutdown_source = ast.get_source_segment(path.read_text(encoding="utf-8"), methods["shutdown"])

    assert "ControlSensorAdapter" in init_source
    assert init_source.index("self.control_adapter") < init_source.index("self.bridge =")
    assert "self.control_adapter.attach(executor)" in run_source
    assert "self.control_adapter.detach(executor)" in run_source
    assert "self.control_adapter.close()" in shutdown_source


@pytest.mark.parametrize(
    "raw",
    [
        {"enabled": "true"},
        {"enabled": True, "required": []},
        {"enabled": True, "required": ["lidar", "lidar"]},
        {"enabled": True, "required": ["lidar", 1]},
        {"enabled": True, "max_age": 0},
        {"enabled": True, "max_age": 0.6},
        {"enabled": True, "parameters": []},
    ],
)
def test_configuration_rejects_unsafe_values(raw):
    with pytest.raises(ValueError):
        ControlSensorConfig.from_mapping(raw)
