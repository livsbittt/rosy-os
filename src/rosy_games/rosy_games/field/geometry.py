"""Pitch numbers. No camera, no ROS."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Field:
    length_m: float = 1.8
    width_m: float = 1.2
    goal_width_m: float = 0.35
    home_id: str = "rosy_01"
    away_id: str = "rosy_02"
    kickoff_radius_m: float = 0.12
    min_spacing_m: float = 0.35

    def in_bounds(self, x: float, y: float) -> bool:
        return abs(x) <= self.length_m / 2 and abs(y) <= self.width_m / 2

    def in_home_goal(self, x: float, y: float) -> bool:
        return x <= -self.length_m / 2 and abs(y) <= self.goal_width_m / 2

    def in_away_goal(self, x: float, y: float) -> bool:
        return x >= self.length_m / 2 and abs(y) <= self.goal_width_m / 2

    def opponent_goal_x(self, robot_id: str) -> float:
        if robot_id == self.home_id:
            return self.length_m / 2
        return -self.length_m / 2
