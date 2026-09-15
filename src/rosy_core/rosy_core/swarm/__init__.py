"""Robot-side follow (SWM-001~007). Navigation executes goals; this package only aims."""

from rosy_core.swarm.poses import ReferencePose, follow_goal

__all__ = ["ReferencePose", "follow_goal"]
