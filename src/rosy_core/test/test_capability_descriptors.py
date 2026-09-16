from rosy_core.domain.capabilities import descriptors_from_cap001

def test_pinky_hardware_flags_map_to_mobility_ids():
    ids = {d.id for d in descriptors_from_cap001({
        "navigation": {"goal_navigation": True, "return_home": True},
        "teleop": True,
        "slam": False,
        "swarm": {"follow": False, "lead": False},
        "docking": {"supported": False},
    })}
    assert "mobility.navigate" in ids
    assert "mobility.move" in ids
    assert "mobility.dock" not in ids
    assert "manipulate.pick" not in ids
    assert "scan_rfid" not in ids
    assert "infer" not in ids


def test_core_slice_has_no_motion_descriptors():
    ids = {d.id for d in descriptors_from_cap001({
        "navigation": {"goal_navigation": False, "return_home": False},
        "teleop": False,
        "slam": False,
        "swarm": {"follow": False, "lead": False},
        "docking": {"supported": False},
    })}
    assert ids == set()
