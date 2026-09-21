"""ROS-free bridge seam for atomic line and traffic-policy application."""

from core_features.command.manager import Twist


def apply_line_candidate(line_follow, traffic_policy, command,
                         line_decision, now: float) -> bool:
    """Apply only when both line and road evidence revisions remain current."""
    result = {"applied": False}

    def apply_line(current) -> None:
        traffic_decision = traffic_policy.gate(
            current.linear, current.angular, now)

        def apply_traffic(gated) -> None:
            command.set_nav_twist(
                Twist(linear=gated.linear, angular=gated.angular),
                now=now,
            )
            result["applied"] = True

        traffic_policy.apply_if_current(traffic_decision, apply_traffic)

    line_follow.apply_if_current(line_decision, apply_line)
    return result["applied"]
