from rosy_core.domain.model import Asset, Component, Device, DeviceState, RuntimeNode, inventory_from_config
from rosy_core.command.arbitration import Mode


def test_inventory_is_a_single_mobile_base_asset():
    data = inventory_from_config(
        {
            "robot": {"id": "rosy_03", "name": "Bay 3", "number": 3},
            "runtime": {"mode": "hardware"},
        },
        profile_model="Pinky Pro",
        sensors=["lidar", "encoder"],
        slices=["core", "motor", "io", "nav"],
        mode=Mode.IDLE,
        health_error=False,
        estop=False,
    )
    assert isinstance(data["node"], RuntimeNode)
    assert data["node"].runtime_mode == "hardware"
    assert data["node"].slices == ("core", "motor", "io", "nav")
    device = data["device"]
    assert isinstance(device, Device)
    assert device.device_id == "rosy_03"
    assert device.device_type == "mobile_base"
    assert {c.name for c in data["components"]} >= {"drive", "lidar", "encoder"}
    asset = data["asset"]
    assert isinstance(asset, Asset)
    assert asset.asset_id == "rosy_03"
    assert asset.type == "mobile_base"
    assert asset.devices == ("rosy_03",)
    assert "omx" not in asset.devices
    assert data["device_state"] is DeviceState.READY


def test_estop_maps_to_safe_stop():
    data = inventory_from_config(
        {"robot": {"id": "rosy_01"}, "runtime": {"mode": "core"}},
        profile_model="Pinky Pro",
        sensors=[],
        slices=["core"],
        mode=Mode.EMERGENCY,
        health_error=False,
        estop=True,
    )
    assert data["device_state"] is DeviceState.SAFE_STOP
