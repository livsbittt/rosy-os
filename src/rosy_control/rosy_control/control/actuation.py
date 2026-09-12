"""Prepare one final calibrated candidate before sweep and hardware publication.

The caller supplies a matching live calibration and permitted actuator caps.
This calculation does not authorize calibration use or physical movement.
"""
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PreparedCommand:
    linear: float
    angular: float
    motor_linear: float


def prepare_command(linear, angular, *, requested_angular, linear_gains, angular_gains,
                    profile_caps, limited_caps, linear_sign):
    def number(value):
        return type(value) in (int, float) and math.isfinite(value)

    def pair(values, low, high=math.inf):
        return (isinstance(values, (tuple, list)) and len(values) == 2 and
                all(number(v) and low <= v <= high for v in values))

    if (not all(number(v) for v in (linear, angular, requested_angular, linear_sign)) or
            linear_sign not in (-1., 1.) or not pair(linear_gains, .75, 1.25) or
            not pair(angular_gains, .75, 1.25) or not pair(profile_caps, 0.) or
            (limited_caps is not None and not pair(limited_caps, 0.))):
        raise ValueError('Invalid final command calibration or limits')
    v, w = linear, angular
    if abs(v) <= .014 and abs(requested_angular) < 1e-4:
        v *= linear_gains[0 if v >= 0. else 1]
    if abs(v) < 1e-4 and abs(w) <= .06:
        w *= angular_gains[0 if w >= 0. else 1]
    scale = min(1., profile_caps[0] / max(abs(v), 1e-12), profile_caps[1] / max(abs(w), 1e-12))
    if limited_caps is not None:
        scale = min(scale, limited_caps[0] / max(abs(v), 1e-12), limited_caps[1] / max(abs(w), 1e-12))
    v, w = v * scale, w * scale
    if not number(v) or not number(w):
        raise ValueError('Final command is not finite')
    return PreparedCommand(v, w, v * linear_sign)
