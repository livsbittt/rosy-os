"""ROS-free proof that line candidates cannot bypass traffic policy."""

from types import SimpleNamespace

import pytest

from core.bridge.traffic_gate import apply_line_candidate
from core.bridge.translate import road_evidence
from core_events.events.bus import EventBus
from core_features.line_follow import (
    LineFollowManager,
    LineFollowMode,
    LineObservation,
)
from core_features.traffic_policy import (
    TrafficPolicyConfig,
    TrafficPolicyManager,
    TrafficPolicyMode,
)


def payload(*, colour="RED", conflict=False, distance=0.08):
    return {
        "source": "CAMERA_ROAD",
        "stamp": 10.0,
        "map_id": "map_260905_update_v2",
        "scene_revision": "road-scene-v1",
        "lane": {"visible": True, "error": 0.0, "confidence": 0.9},
        "stop_line": {
            "visible": True,
            "image_row": 180.0,
            "distance_m": distance,
            "confidence": 0.9,
        },
        "crosswalk": {
            "visible": True,
            "image_row": 150.0,
            "distance_m": 0.16,
            "confidence": 0.8,
        },
        "signal": {
            "visible": colour is not None,
            "colour": colour,
            "confidence": 0.9 if colour else 0.0,
            "conflict": conflict,
        },
    }


def managers(now):
    events = EventBus("rosy_01")
    line = LineFollowManager(events, clock=lambda: now[0])
    line.set_mode(LineFollowMode.CAMERA_LINE)
    line.observe(LineObservation(
        source=LineFollowMode.CAMERA_LINE,
        stamp=10.0,
        visible=True,
        error=0.0,
        confidence=1.0,
    ), received_at=now[0], source_now=10.0)
    traffic = TrafficPolicyManager(
        events,
        config=TrafficPolicyConfig(
            mode=TrafficPolicyMode.ENFORCED,
            map_id="map_260905_update_v2",
            scene_revision="road-scene-v1",
        ),
        clock=lambda: now[0],
    )
    return line, traffic


def test_nested_wire_payload_is_strictly_decoded():
    sample = road_evidence(payload())

    assert sample.stop_line_visible is True
    assert sample.stop_line_distance_m == pytest.approx(0.08)
    assert sample.crosswalk_visible is True
    assert sample.signal_colour == "RED"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.pop("map_id"),
        lambda value: value["signal"].update(conflict="false"),
        lambda value: value["stop_line"].update(visible=1),
        lambda value: value["signal"].update(visible=False, colour="GREEN"),
        lambda value: value["stop_line"].update(distance_m="0.08"),
    ],
)
def test_malformed_wire_payload_is_rejected(mutate):
    value = payload()
    mutate(value)

    with pytest.raises((KeyError, TypeError, ValueError)):
        road_evidence(value)


@pytest.mark.parametrize("colour", ["RED", "YELLOW"])
def test_red_or_yellow_gates_line_candidate_to_zero(colour):
    now = [100.0]
    line, traffic = managers(now)
    sample = road_evidence(payload(colour=colour))
    traffic.observe(sample, received_at=now[0], source_now=sample.stamp)
    command = SimpleNamespace(applied=[])
    command.set_nav_twist = (
        lambda twist, now=None: command.applied.append(twist))

    assert apply_line_candidate(
        line, traffic, command, line.tick(), now[0]) is True

    assert command.applied[-1].linear == 0.0
    assert traffic.status().state == "STOP_REQUIRED"


def test_stale_road_evidence_gates_line_candidate_to_zero():
    now = [100.0]
    line, traffic = managers(now)
    sample = road_evidence(payload(distance=None))
    traffic.observe(sample, received_at=now[0], source_now=sample.stamp)
    now[0] += 0.41
    line.observe(LineObservation(
        source=LineFollowMode.CAMERA_LINE,
        stamp=10.41,
        visible=True,
        error=0.0,
        confidence=1.0,
    ), received_at=now[0], source_now=10.41)
    command = SimpleNamespace(applied=[])
    command.set_nav_twist = (
        lambda twist, now=None: command.applied.append(twist))

    apply_line_candidate(line, traffic, command, line.tick(), now[0])

    assert command.applied[-1].linear == 0.0
    assert traffic.status().reason == "road_evidence_stale"


def test_new_road_evidence_invalidates_precomputed_policy_decision():
    now = [100.0]
    line, traffic = managers(now)
    sample = road_evidence(payload(distance=0.5))
    traffic.observe(sample, received_at=now[0], source_now=sample.stamp)
    decision = traffic.gate(0.08, 0.0)
    conflict = road_evidence(payload(conflict=True))
    traffic.observe(conflict, received_at=now[0], source_now=conflict.stamp)
    applied = []

    assert traffic.apply_if_current(decision, applied.append) is False
    assert applied == []
