"""Robot-side follow (SWM-001~007). Navigation executes goals; this package only aims."""

from rosy_core.swarm.manager import MAX_GOAL_RATE_HZ, SwarmError, SwarmManager
from rosy_core.swarm.poses import ReferencePose, follow_goal

__all__ = [
    "MAX_GOAL_RATE_HZ",
    "ReferencePose",
    "SwarmError",
    "SwarmManager",
    "follow_goal",
]
