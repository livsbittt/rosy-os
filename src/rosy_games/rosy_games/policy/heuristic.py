"""Stage-1 chase. No camera, no neural net."""

from __future__ import annotations

import math

from rosy_games.field import ZERO, Field, Twist
from rosy_games.game import Observation


class HeuristicPolicy:
    def __init__(self, field: Field | None = None, *, speed: float = 0.08) -> None:
        self.field = field or Field()
        self.speed = speed
        self.avoid_m = 0.35

    def act(self, robot_id: str, observation: Observation) -> Twist:
        pose = observation.robots.get(robot_id)
        if pose is None or observation.ball is None:
            return ZERO
        heading = math.atan2(observation.ball.y - pose.y, observation.ball.x - pose.x)
        err = _wrap(heading - pose.yaw)
        turn = max(-1.0, min(1.0, err * 2.0))
        drive = self.speed if abs(err) < 0.4 else 0.0
        goal_x = self.field.opponent_goal_x(robot_id)
        drive += 0.02 if (goal_x - pose.x) * math.cos(pose.yaw) > 0 else 0.0
        other = next((rid for rid in observation.robots if rid != robot_id), None)
        if other is not None:
            opp = observation.robots[other]
            if math.hypot(opp.x - pose.x, opp.y - pose.y) < self.avoid_m:
                drive = min(drive, 0.0)
        return Twist(linear=max(-self.speed, min(self.speed, drive)), angular=turn)


def _wrap(angle: float) -> float:
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle < -math.pi:
        angle += 2 * math.pi
    return angle
