"""Prefix Nav2 TF frames that live under the robot, leave `map` global.

Topics are namespaced by launch. Frames are not. Bringup publishes
`{ns}/odom` → `{ns}/base_footprint` (D-4); stock nav2_params.yaml still
says `odom` / `base_footprint`. AMCL then never sees a transform.
"""

from __future__ import annotations

import copy
from typing import Any

PREFIXABLE_FRAMES = {"odom", "base_footprint", "base_link"}
FRAME_KEYS = {
    "base_frame_id",
    "odom_frame_id",
    "robot_base_frame",
    "global_frame",
    "local_frame",
    "global_frame_id",
}


def apply_nav2_frame_prefix(params: dict, prefix: str) -> dict:
    data = copy.deepcopy(params)
    if not prefix:
        return data
    if not prefix.endswith("/"):
        prefix += "/"

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, (dict, list)):
                    walk(value)
                elif (
                    key in FRAME_KEYS
                    and isinstance(value, str)
                    and value in PREFIXABLE_FRAMES
                ):
                    obj[key] = prefix + value
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    return data
