"""rosy_core.services — 의존성 컨테이너 (API/WS가 접근하는 서비스 집합)."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from rosy_core.capability import Capability
from rosy_core.command.arbitration import ModeMachine, SourceRegistry
from rosy_core.command.manager import CommandManager
from rosy_core.events.bus import EventBus
from rosy_core.identity import RobotIdentity
from rosy_core.navigation.manager import NavigationManager
from rosy_core.profile import RobotProfile
from rosy_core.safety.manager import BatteryPolicy, SafetyManager, SpeedLimits
from rosy_core.state.manager import StateManager
from rosy_core.system.runtime import HostRuntimeProbe
from rosy_core.waypoints.manager import WaypointManager


@dataclass
class CoreServices:
    config: dict[str, Any]
    identity: RobotIdentity
    profile: Optional[RobotProfile]
    capability: Capability
    events: EventBus
    state: StateManager
    registry: SourceRegistry
    modes: ModeMachine
    command: CommandManager
    safety: SafetyManager
    waypoints: WaypointManager
    nav: NavigationManager
    runtime_probe: HostRuntimeProbe
    started_at: float = field(default_factory=time.time)

    @classmethod
    def build(cls, config: dict[str, Any], profile: RobotProfile,
              capability_data: dict, waypoints_path) -> "CoreServices":
        robot_id = config.get("robot", {}).get("id", "rosy_01")
        events = EventBus(robot_id, buffer_size=int(config.get("events", {}).get("ring_buffer_size", 1000)))

        safety_cfg = config.get("safety", {})
        nav_cfg = config.get("navigation", {})
        limits = SpeedLimits(
            max_linear=float(profile.max_linear_velocity or nav_cfg.get("max_linear_velocity", 0.20)),
            max_angular=float(profile.max_angular_velocity or nav_cfg.get("max_angular_velocity", 0.80)),
            manual_linear=float(safety_cfg.get("manual_linear", 0.15)),
            manual_angular=float(safety_cfg.get("manual_angular", 0.60)),
            fleet_linear=float(safety_cfg.get("fleet_linear", nav_cfg.get("max_linear_velocity", 0.20))),
            fleet_angular=float(safety_cfg.get("fleet_angular", nav_cfg.get("max_angular_velocity", 0.80))),
        )
        battery_policy = BatteryPolicy(
            warning_percent=float(safety_cfg.get("battery_warning_percent", 20)),
            critical_percent=float(safety_cfg.get("battery_critical_percent", 10)),
            critical_action=str(safety_cfg.get("battery_critical_policy", "RETURN_HOME")),
        )
        safety = SafetyManager(limits, battery_policy,
                               fleet_loss_policy=str(safety_cfg.get("fleet_loss_policy", "STOP")),
                               events=events)

        identity = RobotIdentity.from_config(config, profile_model=profile.model)
        capability = Capability(capability_data)
        state = StateManager(robot_id)
        registry = SourceRegistry(config.get("command_sources"))
        modes = ModeMachine()
        command = CommandManager(registry, modes, safety, events=events)
        waypoints = WaypointManager(waypoints_path, events=events)
        nav = NavigationManager(events, state, waypoints, safety,
                                stuck_timeout_s=float(safety_cfg.get("stuck_timeout_s", 30.0)))
        runtime_probe = HostRuntimeProbe(
            host_root=os.environ.get("ROSY_HOST_ROOT", "/"),
            data_path=waypoints_path.parent,
        )
        return cls(config=config, identity=identity, profile=profile, capability=capability,
                   events=events, state=state, registry=registry, modes=modes,
                   command=command, safety=safety, waypoints=waypoints, nav=nav,
                   runtime_probe=runtime_probe)
