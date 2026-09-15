"""Opt-in capability advertisement for tests that exercise served routes."""

SERVING_CAPS = {
    "navigation": {
        "goal_navigation": True,
        "return_home": True,
        "max_linear_velocity": 0.20,
        "max_angular_velocity": 0.80,
    },
    "teleop": True,
    "slam": True,
    "swarm": {"follow": True, "lead": True},
}
