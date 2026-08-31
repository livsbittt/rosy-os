"""Deployment environment overrides that keep ROS graph and TF aligned."""

import rosy_core.config as config_module


def test_ros_namespace_derives_core_frame_prefix(tmp_path, monkeypatch):
    config_path = tmp_path / "rosy.yaml"
    config_path.write_text("robot:\n  frame_prefix: ''\n", encoding="utf-8")
    monkeypatch.setattr(config_module, "LOCAL_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.delenv("ROSY_CONFIG", raising=False)
    monkeypatch.setenv("ROSY_NAMESPACE", "/rosy_07/")

    config = config_module.load_config(str(config_path))

    assert config["robot"]["frame_prefix"] == "rosy_07/"
