from rosy_core.domain.capabilities import descriptors_from_cap001
from rosy_core.domain.model import DeviceState
from rosy_core.domain.tasks import TaskKind

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


_PINKY_FLAGS = {
    "navigation": {"goal_navigation": True, "return_home": True},
    "teleop": True,
    "slam": True,
    "swarm": {"follow": True, "lead": True},
    "docking": {"supported": False},
}


def test_safe_stop_keeps_ids_but_marks_them_unavailable():
    descriptors = descriptors_from_cap001(
        _PINKY_FLAGS, device_state=DeviceState.SAFE_STOP
    )
    by_id = {d.id: d.available for d in descriptors}
    assert by_id["mobility.move"] is False
    assert by_id["mobility.navigate"] is False
    assert "manipulate.pick" not in by_id


def test_ready_marks_advertised_descriptors_available():
    descriptors = descriptors_from_cap001(
        _PINKY_FLAGS, device_state=DeviceState.READY
    )
    by_id = {d.id: d.available for d in descriptors}
    assert by_id["mobility.move"] is True
    assert by_id["perception.localize"] is True


def test_task_kinds_require_concept_ids_not_hardware_names():
    assert TaskKind.MOVE.concept_id == "mobility.move"
    assert TaskKind.NAVIGATE.concept_id == "mobility.navigate"
    assert TaskKind.FOLLOW.concept_id == "mobility.follow"
    assert TaskKind.DOCK.concept_id == "mobility.dock"
    assert TaskKind.MOVE.capability == "teleop"
