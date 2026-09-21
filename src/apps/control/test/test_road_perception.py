import numpy as np
import pytest

from control.sensing.road import (
    RoadObservation,
    detect_road_observation,
    road_observation_payload,
)


WIDTH = 320
HEIGHT = 240


def _frame(*, lane_x=None, stop_y=None, crosswalk_rows=(), signals=()):
    frame = np.full((HEIGHT, WIDTH, 3), 35, dtype=np.uint8)
    if lane_x is not None:
        frame[70:, lane_x - 4:lane_x + 4] = (235, 235, 235)
    if stop_y is not None:
        frame[stop_y - 3:stop_y + 3, 55:265] = (245, 245, 245)
    for row in crosswalk_rows:
        frame[row - 2:row + 2, 75:245] = (245, 245, 245)
    colours = {
        "RED": (0, 0, 255),
        "YELLOW": (0, 255, 255),
        "GREEN": (0, 255, 0),
    }
    for index, colour in enumerate(signals):
        x0 = 20 + index * 28
        frame[20:38, x0:x0 + 18] = colours[colour]
    return frame


def test_lane_centroid_ignores_horizontal_stop_and_crosswalk_markings():
    observation = detect_road_observation(
        _frame(lane_x=220, stop_y=190, crosswalk_rows=(120, 132, 144, 156)))

    assert isinstance(observation, RoadObservation)
    assert observation.lane is not None
    assert observation.lane.error == pytest.approx((220 - 160) / 160, abs=0.04)
    assert observation.stop_line is not None
    assert observation.crosswalk is not None


def test_single_wide_horizontal_group_is_a_stop_line_not_a_crosswalk():
    observation = detect_road_observation(_frame(lane_x=160, stop_y=180))

    assert observation.stop_line is not None
    assert observation.stop_line.image_row == pytest.approx(180, abs=3)
    assert observation.crosswalk is None


def test_repeated_wide_horizontal_groups_are_a_crosswalk():
    observation = detect_road_observation(
        _frame(lane_x=160, crosswalk_rows=(125, 137, 149, 161)))

    assert observation.crosswalk is not None
    assert observation.crosswalk.image_row == pytest.approx(161, abs=4)
    assert observation.stop_line is None


@pytest.mark.parametrize("colour", ["RED", "YELLOW", "GREEN"])
def test_upper_image_traffic_signal_colour_is_recognized(colour):
    observation = detect_road_observation(
        _frame(lane_x=160, signals=(colour,)))

    assert observation.signal is not None
    assert observation.signal.colour == colour
    assert observation.signal.confidence > 0.5
    assert observation.signal_conflict is False


def test_multiple_signal_colours_fail_as_conflicting_evidence():
    observation = detect_road_observation(
        _frame(lane_x=160, signals=("RED", "GREEN")))

    assert observation.signal is None
    assert observation.signal_conflict is True


def test_blank_frame_reports_no_features_without_inventing_distance():
    observation = detect_road_observation(_frame())

    assert observation.lane is None
    assert observation.stop_line is None
    assert observation.crosswalk is None
    assert observation.signal is None
    assert observation.signal_conflict is False


def test_validated_ground_model_supplies_metric_feature_distance():
    class Ground:
        def distance(self, row, column=None):
            assert column == pytest.approx(WIDTH / 2)
            return row / 1000.0

    observation = detect_road_observation(
        _frame(lane_x=160, stop_y=180), ground=Ground())

    assert observation.stop_line is not None
    assert observation.stop_line.distance_m == pytest.approx(0.18, abs=0.01)


def test_payload_is_strict_json_shape_and_observations_are_immutable():
    observation = detect_road_observation(
        _frame(lane_x=160, stop_y=180, signals=("RED",)))

    payload = road_observation_payload(
        "CAMERA_ROAD", 12.5, "map_260905_update_v2",
        "road-scene-v1", observation)

    assert payload == {
        "source": "CAMERA_ROAD",
        "stamp": 12.5,
        "map_id": "map_260905_update_v2",
        "scene_revision": "road-scene-v1",
        "lane": {
            "visible": True,
            "error": pytest.approx(0.0, abs=0.02),
            "confidence": pytest.approx(observation.lane.confidence),
        },
        "stop_line": {
            "visible": True,
            "image_row": pytest.approx(180, abs=3),
            "distance_m": None,
            "confidence": pytest.approx(observation.stop_line.confidence),
        },
        "crosswalk": {
            "visible": False,
            "image_row": None,
            "distance_m": None,
            "confidence": 0.0,
        },
        "signal": {
            "visible": True,
            "colour": "RED",
            "confidence": pytest.approx(observation.signal.confidence),
            "conflict": False,
        },
    }
    with pytest.raises((AttributeError, TypeError)):
        observation.signal_conflict = True


@pytest.mark.parametrize(
    "args",
    [
        ("IR_LINE", 1.0, "map", "scene"),
        ("CAMERA_ROAD", float("nan"), "map", "scene"),
        ("CAMERA_ROAD", 1.0, "", "scene"),
        ("CAMERA_ROAD", 1.0, "map", ""),
    ],
)
def test_payload_rejects_unbound_or_invalid_evidence(args):
    with pytest.raises(ValueError):
        road_observation_payload(*args, detect_road_observation(_frame()))
