"""The two reconcile latches differ, and the difference is the point.

Both live at 5 Hz in `ros_bridge.py`, where no host test reaches them. LED
latches even when its service is missing; LiDAR does not, because it is a
navigation input and a late driver must still be reached. Getting that backwards
is silent: the robot simply never spins its lidar, or repaints the same colour
five times a second forever.
"""

from __future__ import annotations

from rosy_core.bridge.reconcile import reconcile


def test_no_action_when_nothing_changed():
    calls = []
    acted, applied = reconcile("red", "red", lambda: calls.append(1) or True,
                               latch_on_skip=True)

    assert acted is False
    assert applied == "red"
    assert calls == []


def test_acts_and_latches_when_the_desire_changes():
    acted, applied = reconcile("green", "red", lambda: True, latch_on_skip=False)

    assert acted is True
    assert applied == "green"


def test_led_latches_even_though_the_service_was_missing():
    """Decoration: skipping is fine, repainting at 5 Hz is not."""
    acted, applied = reconcile("green", "red", lambda: False, latch_on_skip=True)

    assert acted is False
    assert applied == "green", "a skipped LED call must not be retried"


def test_lidar_does_not_latch_when_the_service_was_missing():
    """Navigation input: a driver that comes up late must still be reached."""
    acted, applied = reconcile(True, False, lambda: False, latch_on_skip=False)

    assert acted is False
    assert applied is False, "an unsent lidar command must be retried next tick"


def test_lidar_retries_until_the_service_appears_then_stops():
    ready = iter([False, False, True])
    applied = False
    attempts = 0

    for _ in range(4):
        def send():
            nonlocal attempts
            attempts += 1
            return next(ready, True)

        _acted, applied = reconcile(True, applied, send, latch_on_skip=False)

    assert applied is True
    assert attempts == 3, "stops attempting once the command has landed"


def test_false_is_a_value_not_an_absence():
    """`spinning=False` must be latchable — a stop command is a command."""
    acted, applied = reconcile(False, True, lambda: True, latch_on_skip=False)

    assert acted is True
    assert applied is False
