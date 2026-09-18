"""Apply CycloneDDS before rclpy.init (D-121). Does not import rclpy."""

from __future__ import annotations

from typing import MutableMapping

REQUIRED_RMW = "rmw_cyclonedds_cpp"


class RmwError(ValueError):
    """RMW is set to something Rosy will not run."""


def apply_cyclone_rmw(env: MutableMapping[str, str]) -> str:
    """Fill empty RMW with Cyclone. Refuse a foreign implementation.

    Must run before ``rclpy.init``. Changing env afterwards does not retarget
    an already loaded RMW.
    """
    current = str(env.get("RMW_IMPLEMENTATION") or "").strip()
    if not current:
        env["RMW_IMPLEMENTATION"] = REQUIRED_RMW
        return REQUIRED_RMW
    if current != REQUIRED_RMW:
        raise RmwError(
            f"RMW_IMPLEMENTATION={current}; Rosy requires {REQUIRED_RMW}"
        )
    return current
