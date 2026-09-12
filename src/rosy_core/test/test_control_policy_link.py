"""Real CORE arbitration consuming the absorbed Control semantic policy."""
from dataclasses import replace
from pathlib import Path

import pytest

from rosy_core.command.arbitration import Mode, ModeMachine, SourceRegistry
from rosy_core.command.manager import CommandManager, Twist
from rosy_core.safety.manager import SafetyManager, SpeedLimits, BatteryPolicy


@pytest.fixture
def linked(monkeypatch):
    # Host tests use the absorbed package in this checkout, never the archive.
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'rosy_control'))
    from rosy_control.control.command_gate import CommandPolicy, GateInputs, GateSnapshot
    policy = CommandPolicy('revision-1')
    safety = SafetyManager(SpeedLimits(), BatteryPolicy())
    modes = ModeMachine()
    command = CommandManager(SourceRegistry(), modes, safety)
    safety.bind_control_policy(policy)
    modes.transition(Mode.NAVIGATION)
    snapshot = GateSnapshot(policy.session, 1, 'revision-1', 10., 10.2, GateInputs())
    assert policy.update(snapshot)
    return command, safety, modes, policy, snapshot


def test_real_control_obstacle_restriction_and_explicit_escape(linked):
    command, safety, modes, policy, snapshot = linked
    assert policy.update(replace(snapshot, sequence=2, inputs=replace(snapshot.inputs, obstacle=True)))
    command.set_nav_twist(Twist(.1, 0.), now=10.)
    assert command.select_output(now=10.01) == Twist()
    assert not safety.estop
    command.set_nav_twist(Twist(-.1, 0.), now=10.02)
    assert command.select_output(now=10.03) == Twist(-.1, 0.)
    command.set_nav_twist(Twist(0., .2), now=10.04)
    assert command.select_output(now=10.05) == Twist(0., .2)


def test_expired_observation_stops_a_fresh_command(linked):
    command, safety, modes, policy, snapshot = linked
    command.set_nav_twist(Twist(.1, 0.), now=10.21)
    assert command.select_output(now=10.22) == Twist()
    assert safety.estop


def test_repeated_read_or_replayed_update_cannot_extend_observation(linked):
    command, safety, modes, policy, snapshot = linked
    assert not policy.update(replace(snapshot, expires_at=10.4))
    command.set_nav_twist(Twist(.1, 0.), now=10.)
    assert command.select_output(now=10.1) == Twist(.1, 0.)
    command.set_nav_twist(Twist(.1, 0.), now=10.25)
    assert command.select_output(now=10.26) == Twist()
    assert safety.estop


@pytest.mark.parametrize('changes', [
    {'calibration_revision': 'other'}, {'session': 'previous-process'},
    {'observed_at': 11.}, {'expires_at': 12.}, {'sequence': True},
])
def test_invalid_or_wrong_identity_snapshot_cannot_authorize_motion(linked, changes):
    command, safety, modes, policy, snapshot = linked
    policy.invalidate()
    policy.update(replace(snapshot, **({'sequence': 2} | changes)))
    command.set_nav_twist(Twist(.1, 0.), now=10.)
    assert command.select_output(now=10.01) == Twist()
    assert safety.estop


def test_rebinding_policy_discards_old_candidate(linked):
    command, safety, modes, policy, snapshot = linked
    command.set_nav_twist(Twist(.1, 0.), now=10.)
    safety.bind_control_policy(policy)
    assert command.select_output(now=10.01) == Twist()


def test_new_sequence_cannot_refresh_the_same_sensor_sample(linked):
    command, safety, modes, policy, snapshot = linked
    assert not policy.update(replace(snapshot, sequence=2, expires_at=10.4))
    command.set_nav_twist(Twist(.1, 0.), now=10.25)
    assert command.select_output(now=10.26) == Twist()
    assert safety.estop


@pytest.mark.parametrize('changes', [{'pickup': True}, {'localization_ready': False},
                                   {'observation_failure': 'imu_unavailable'},
                                   {'legacy_tilt_recovery': True}, {'bounded_motion': True},
                                   {'can_rotate': 1}, {'profile_valid': 'true'}])
def test_hazard_or_unintegrated_actuation_mode_stops(linked, changes):
    command, safety, modes, policy, snapshot = linked
    policy.update(replace(snapshot, sequence=2, inputs=replace(snapshot.inputs, **changes)))
    command.set_nav_twist(Twist(.1, 0.), now=10.)
    assert command.select_output(now=10.01) == Twist()
    assert safety.estop
