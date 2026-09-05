"""Deployment environment overrides that keep ROS graph and TF aligned."""

from pathlib import Path
import xml.etree.ElementTree as ET

import yaml

import rosy_core.config as config_module
from rosy_core.config import ConfigError, patch_local_config
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


def test_patch_local_config_merges_safety_limits_without_clobbering(tmp_path):
    overlay = tmp_path / "rosy.yaml"
    overlay.write_text("robot:\n  id: rosy_keep\nauth:\n  tokens: []\n", encoding="utf-8")

    written = patch_local_config(
        {"safety": {"manual_linear": 0.11, "manual_angular": 0.42}},
        path=overlay,
    )

    saved = yaml.safe_load(written.read_text(encoding="utf-8"))
    assert saved["robot"]["id"] == "rosy_keep"
    assert saved["auth"]["tokens"] == []
    assert saved["safety"]["manual_linear"] == 0.11
    assert saved["safety"]["manual_angular"] == 0.42


def test_overlay_path_prefers_rosy_config_env(tmp_path, monkeypatch):
    env_overlay = tmp_path / "env.yaml"
    monkeypatch.setenv("ROSY_CONFIG", str(env_overlay))
    monkeypatch.setattr(config_module, "LOCAL_CONFIG_PATH", tmp_path / "home.yaml")
    assert config_module.overlay_path() == env_overlay


def test_patch_local_config_rejects_non_mapping_overlay(tmp_path):
    overlay = tmp_path / "rosy.yaml"
    overlay.write_text("- not a mapping\n", encoding="utf-8")
    try:
        patch_local_config({"safety": {"manual_linear": 0.01}}, path=overlay)
    except ConfigError as exc:
        assert "mapping" in str(exc)
    else:
        raise AssertionError("non-mapping overlay must be rejected")


def test_patch_local_config_removes_temp_file_on_replace_failure(tmp_path, monkeypatch):
    overlay = tmp_path / "rosy.yaml"

    def boom(_src, _dst):
        raise OSError("replace failed")

    monkeypatch.setattr(config_module.os, "replace", boom)
    try:
        patch_local_config({"safety": {"manual_linear": 0.1}}, path=overlay)
    except OSError:
        pass
    else:
        raise AssertionError("expected replace failure")
    assert not overlay.exists()
    assert not overlay.with_name("rosy.yaml.tmp").exists()


def test_patch_local_config_creates_overlay_and_refuses_package_default(tmp_path):
    overlay = tmp_path / ".rosy" / "rosy.yaml"
    written = patch_local_config({"safety": {"manual_linear": 0.08}}, path=overlay)
    assert written.exists()
    assert yaml.safe_load(written.read_text(encoding="utf-8"))["safety"]["manual_linear"] == 0.08

    default = config_module._find_default_config()
    try:
        patch_local_config({"safety": {"manual_linear": 0.01}}, path=default)
    except ConfigError as exc:
        assert "package default" in str(exc)
    else:
        raise AssertionError("must not write the packaged rosy_default.yaml")


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
