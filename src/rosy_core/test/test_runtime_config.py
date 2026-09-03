"""Deployment environment overrides that keep ROS graph and TF aligned."""

from pathlib import Path
import xml.etree.ElementTree as ET

import rosy_core.config as config_module
from rosy_core.identity import SOFTWARE_VERSION


def test_runtime_mode_env_overrides_config(tmp_path, monkeypatch):
    config_path = tmp_path / "rosy.yaml"
    config_path.write_text("runtime:\n  mode: core\n", encoding="utf-8")
    monkeypatch.setattr(config_module, "LOCAL_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.delenv("ROSY_CONFIG", raising=False)
    monkeypatch.setenv("ROSY_RUNTIME_MODE", "hardware")

    config = config_module.load_config(str(config_path))

    assert config["runtime"]["mode"] == "hardware"


def test_unknown_runtime_mode_env_is_rejected(tmp_path, monkeypatch):
    config_path = tmp_path / "rosy.yaml"
    config_path.write_text("robot:\n  id: rosy_01\n", encoding="utf-8")
    monkeypatch.setattr(config_module, "LOCAL_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.delenv("ROSY_CONFIG", raising=False)
    monkeypatch.setenv("ROSY_RUNTIME_MODE", "io")

    try:
        config_module.load_config(str(config_path))
    except ValueError as exc:
        assert "io" in str(exc)
    else:
        raise AssertionError("unknown ROSY_RUNTIME_MODE must not boot")


def test_ros_namespace_derives_core_frame_prefix(tmp_path, monkeypatch):
    config_path = tmp_path / "rosy.yaml"
    config_path.write_text("robot:\n  frame_prefix: ''\n", encoding="utf-8")
    monkeypatch.setattr(config_module, "LOCAL_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.delenv("ROSY_CONFIG", raising=False)
    monkeypatch.delenv("ROSY_RUNTIME_MODE", raising=False)
    monkeypatch.setenv("ROSY_NAMESPACE", "/rosy_07/")

    config = config_module.load_config(str(config_path))

    assert config["robot"]["frame_prefix"] == "rosy_07/"


def test_software_version_has_one_source():
    root = Path(__file__).resolve().parents[1]
    node_src = (root / "rosy_core" / "node.py").read_text(encoding="utf-8")
    assert "from rosy_core.identity import SOFTWARE_VERSION" in node_src
    assert 'SOFTWARE_VERSION = "' not in node_src
    tree = ET.parse(root / "package.xml")
    version = tree.find("{http://www.ros.org/schema/package_format3.xsd}version")
    if version is None:
        version = tree.find("version")
    assert version is not None
    assert version.text == SOFTWARE_VERSION
