"""rosy_core.identity — IDN-001~003 (P1-2). ROS 무의존."""

from __future__ import annotations

import os
import re
import socket
from typing import Any, Optional

SOFTWARE_VERSION = "0.1.0"
ROBOT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def validate_robot_id(robot_id: str) -> str:
    value = (robot_id or "").strip()
    if not ROBOT_ID_PATTERN.fullmatch(value):
        raise ValueError("robot id must be lowercase letters, digits, underscore or hyphen")
    return value


def validate_robot_name(name: str) -> str:
    value = (name or "").strip()
    if not value or len(value) > 64:
        raise ValueError("robot name must be 1 to 64 characters")
    return value


def _primary_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.0)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class RobotIdentity:
    def __init__(self, robot_id: str, robot_name: str, profile_model: str = "unknown",
                 serial: Optional[str] = None, hardware_version: Optional[str] = None,
                 runtime_mode: str = "core", robot_number: Optional[int] = None) -> None:
        self.robot_id = robot_id
        self.robot_name = robot_name
        self.profile_model = profile_model
        self.serial = serial
        self.hardware_version = hardware_version
        self.runtime_mode = runtime_mode
        self.robot_number = robot_number

    @classmethod
    def from_config(cls, config: dict[str, Any], profile_model: str = "unknown") -> "RobotIdentity":
        robot = config.get("robot") or {}
        mode = str((config.get("runtime") or {}).get("mode") or "core")
        number = robot.get("number")
        if number is not None:
            number = int(number)
        return cls(
            robot_id=robot.get("id") or "rosy_01",
            robot_name=robot.get("name") or "Rosy 01",
            profile_model=profile_model,
            serial=robot.get("serial"),
            hardware_version=robot.get("hardware_version"),
            runtime_mode=mode,
            robot_number=number,
        )

    def info(self) -> dict[str, Any]:
        """IDN-003 응답 스키마 (API Ref §5.1)."""
        return {
            "robot_id": self.robot_id,
            "robot_name": self.robot_name,
            "robot_number": self.robot_number,
            "hostname": socket.gethostname(),
            "ip_address": _primary_ip(),
            "hardware_model": self.profile_model,
            "hardware_version": self.hardware_version,
            "serial_number": self.serial,
            "software_version": SOFTWARE_VERSION,
            "ros_version": os.environ.get("ROS_DISTRO", "unknown"),
            "runtime_mode": self.runtime_mode,
            "uptime_seconds": None,
        }
