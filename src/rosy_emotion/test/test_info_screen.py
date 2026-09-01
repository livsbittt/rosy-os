"""PWR-003 정보 카드 렌더러 단위 테스트 — ROS/LCD 없이 순수 PIL."""

import pytest

from rosy_emotion.info_screen import DEFAULT_SIZE, battery_color, render


class TestBatteryColor:
    @pytest.mark.parametrize("percent,expected", [
        (100.0, (64, 200, 120)),
        (60.0, (64, 200, 120)),
        (59.9, (240, 180, 60)),
        (30.0, (240, 180, 60)),
        (29.9, (232, 80, 80)),
        (0.0, (232, 80, 80)),
    ])
    def test_thresholds(self, percent, expected):
        assert battery_color(percent) == expected


class TestRender:
    def _payload(self, **overrides):
        payload = {
            "robot_id": "rosy_01",
            "battery_percent": 73.4,
            "battery_voltage": 12.1,
            "mode": "IDLE",
            "navigation": "IDLE",
            "health": "OK",
            "estop": False,
            "address": "http://192.168.0.7:8080",
        }
        payload.update(overrides)
        return payload

    def test_default_size_and_mode(self):
        image = render(self._payload())
        assert image.size == DEFAULT_SIZE
        assert image.mode == "RGB"

    def test_custom_size(self):
        image = render(self._payload(), size=(480, 320))
        assert image.size == (480, 320)

    def test_empty_payload_still_renders(self):
        # 스냅샷이 아직 안 찼거나 필드가 비어도 화면은 반드시 나와야 한다.
        image = render({})
        assert image.size == DEFAULT_SIZE

    def test_missing_voltage_is_tolerated(self):
        assert render(self._payload(battery_voltage=None)).size == DEFAULT_SIZE

    @pytest.mark.parametrize("percent", [-20.0, 0.0, 100.0, 150.0])
    def test_gauge_clamps_out_of_range_percent(self, percent):
        assert render(self._payload(battery_percent=percent)).size == DEFAULT_SIZE

    def test_gauge_is_painted_in_the_battery_color(self):
        # 게이지 채움 영역(좌상단 안쪽)이 실제로 잔량 색으로 칠해져야 한다.
        for percent in (5.0, 45.0, 90.0):
            image = render(self._payload(battery_percent=percent))
            assert image.getpixel((22, 113)) == battery_color(percent)

    def test_estop_payload_renders(self):
        assert render(self._payload(estop=True)).size == DEFAULT_SIZE
