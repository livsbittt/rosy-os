"""Semantic command restrictions shared by the legacy node and CORE adapters.

This layer consumes already classified sensor state. It neither establishes
sensor freshness nor replaces the downstream calibrated swept-footprint check.
"""
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class GateInputs:
    estop: bool = False
    profile_valid: bool = True
    observation_failure: str | None = None
    localization_ready: bool = True
    pickup: bool = False
    obstacle_hold: str | None = None
    command_age: float = 0.
    rotation_trial: bool = False
    translation_trial: bool = False
    tilt: bool = False
    rear_blocked: bool = False
    obstacle: bool = False
    cliff: bool = False
    can_rotate: bool = True
    bounded_motion: bool = False
    legacy_tilt_recovery: bool = False


@dataclass(frozen=True)
class GateResult:
    linear: float
    angular: float
    reason: str
    discard: bool = False


def evaluate_command(linear: float, angular: float, state: GateInputs) -> GateResult:
    def stop(reason, discard=False):
        return GateResult(0., 0., reason, discard)

    if state.estop:
        return stop('estop', True)
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
               for v in (linear, angular)):
        return stop('invalid_command', True)
    if not state.profile_valid or state.observation_failure:
        return stop(state.observation_failure or 'invalid_geometry', True)
    if not state.localization_ready:
        return stop('localization_unavailable', True)
    if state.pickup:
        return stop('pickup')
    if state.obstacle_hold:
        return stop(state.obstacle_hold)
    age_valid = (isinstance(state.command_age, (int, float)) and
                 not isinstance(state.command_age, bool) and math.isfinite(state.command_age) and
                 state.command_age >= 0.)
    if not age_valid or (state.command_age > .5 and not (state.tilt and state.legacy_tilt_recovery)):
        return stop('command_stale')
    if state.rotation_trial and (linear != 0. or abs(angular) > .06):
        return stop('rotation_trial_domain')
    if state.translation_trial and (angular != 0. or abs(linear) > .014):
        return stop('translation_trial_domain')

    v, w = linear, angular
    # Only the legacy comparison runtime may synthesize this recovery candidate.
    # CORE recovery must submit its own candidate through the command arbiter.
    if state.tilt and state.legacy_tilt_recovery and not state.rear_blocked and v >= 0.:
        v = -.003
    elif state.tilt and state.rear_blocked:
        v = 0.
    if (state.obstacle or state.cliff or state.tilt) and v > 0.:
        v = 0.
    if v < 0. and state.rear_blocked:
        v = 0.
    if not state.can_rotate and not state.bounded_motion:
        w = 0.
    if linear != 0. and angular != 0. and (v != linear or w != angular):
        return stop('trajectory_changed')
    return GateResult(v, w, 'allow' if (v, w) == (linear, angular) else 'motion_limited')
