"""rosy_core.identity — IDN-001~003 (P1-2). ROS 무의존."""

from __future__ import annotations

import os
import re
import socket
from typing import Any, Optional

SOFTWARE_VERSION = "0.1.0"
ROBOT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class IdentityError(ValueError):
    """API robot_id does not match the robot-number identity (D-63)."""


def _parse_robot_number(raw: str) -> int:
    value = raw.strip()
    if not value or not value.isdigit() or (len(value) > 1 and value.startswith("0")):
        raise IdentityError(f"ROSY_ROBOT_NUMBER {raw!r} is not a plain decimal")
    number = int(value)
    if not 0 <= 40 + number <= 101:
        raise IdentityError(f"ROSY_ROBOT_NUMBER {number} is outside the Linux-safe domain range")
    return number


def derived_robot_id(environ: Optional[dict[str, str]] = None) -> Optional[str]:
    env = os.environ if environ is None else environ
    number_raw = str(env.get("ROSY_ROBOT_NUMBER", "") or "").strip()
    namespace = str(env.get("ROSY_NAMESPACE", "") or "").strip().strip("/")
    from_number = f"rosy_{_parse_robot_number(number_raw):02d}" if number_raw else None
    if from_number and namespace and namespace != from_number:
        raise IdentityError(
            f"ROSY_NAMESPACE {namespace!r} does not match robot number id {from_number!r}"
        )
    return from_number or (namespace or None)


def resolve_robot_id(config: dict[str, Any], environ: Optional[dict[str, str]] = None) -> str:
    derived = derived_robot_id(environ)
    configured = (config.get("robot") or {}).get("id")
    if configured:
        configured = validate_robot_id(str(configured))
    if derived and configured and configured != derived:
        raise IdentityError(
            f"robot.id {configured!r} does not match derived identity {derived!r}"
        )
    robot_id = derived or configured
    if not robot_id:
        raise IdentityError("robot identity is missing")
    return robot_id


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
                 runtime_mode: str = "core") -> None:
        self.robot_id = robot_id
        self.robot_name = robot_name
        self.profile_model = profile_model
        self.serial = serial
        self.hardware_version = hardware_version
        self.runtime_mode = runtime_mode

    @classmethod
    def from_config(cls, config: dict[str, Any], profile_model: str = "unknown") -> "RobotIdentity":
        robot = config.get("robot", {})
        mode = str((config.get("runtime") or {}).get("mode") or "core")
        return cls(
            robot_id=resolve_robot_id(config),
            robot_name=validate_robot_name(str(robot.get("name") or "Rosy")),
            profile_model=profile_model,
            serial=robot.get("serial"),
            hardware_version=robot.get("hardware_version"),
            runtime_mode=mode,
        )

    def info(self) -> dict[str, Any]:
        """IDN-003 응답 스키마 (API Ref §5.1)."""
        return {
            "robot_id": self.robot_id,
            "robot_name": self.robot_name,
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
