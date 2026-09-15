"""D-63: API robot_id is the name derived from the robot number."""

from __future__ import annotations

import pytest

from rosy_core.identity import IdentityError, RobotIdentity, resolve_robot_id


def test_host_yaml_id_is_used_when_no_device_identity_env(monkeypatch):
    monkeypatch.delenv("ROSY_ROBOT_NUMBER", raising=False)
    monkeypatch.delenv("ROSY_NAMESPACE", raising=False)

    robot_id = resolve_robot_id({"robot": {"id": "rosy_01", "name": "Rosy 01"}})

    assert robot_id == "rosy_01"


def test_robot_number_derives_api_id(monkeypatch):
    monkeypatch.setenv("ROSY_ROBOT_NUMBER", "7")
    monkeypatch.delenv("ROSY_NAMESPACE", raising=False)

    robot_id = resolve_robot_id({"robot": {"id": "rosy_07", "name": "unit"}})

    assert robot_id == "rosy_07"


def test_yaml_id_that_disagrees_with_robot_number_is_refused(monkeypatch):
    monkeypatch.setenv("ROSY_ROBOT_NUMBER", "7")
    monkeypatch.delenv("ROSY_NAMESPACE", raising=False)

    with pytest.raises(IdentityError, match="rosy_01"):
        resolve_robot_id({"robot": {"id": "rosy_01"}})


def test_namespace_that_disagrees_with_robot_number_is_refused(monkeypatch):
    monkeypatch.setenv("ROSY_ROBOT_NUMBER", "7")
    monkeypatch.setenv("ROSY_NAMESPACE", "rosy_02")

    with pytest.raises(IdentityError, match="rosy_02"):
        resolve_robot_id({"robot": {}})


def test_from_config_does_not_invent_rosy_01_when_id_is_missing(monkeypatch):
    monkeypatch.delenv("ROSY_ROBOT_NUMBER", raising=False)
    monkeypatch.delenv("ROSY_NAMESPACE", raising=False)

    with pytest.raises(IdentityError, match="missing"):
        RobotIdentity.from_config({"robot": {}, "runtime": {"mode": "core"}})
