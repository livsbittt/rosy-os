"""rosy_core.services — 의존성 컨테이너 (API/WS가 접근하는 서비스 집합)."""

from __future__ import annotations

import os
from pathlib import Path
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from rosy_core.capability import Capability
from rosy_core.command.arbitration import ModeMachine, SourceRegistry
from rosy_core.command.manager import CommandManager
from rosy_core.docking.agent import DockAgent
from rosy_core.docking.database import DockDatabase
from rosy_core.docking.detector import SimulatedDetector
from rosy_core.docking.manager import DockingConfig, DockingManager
from rosy_core.protocol.schemas import DockState
from rosy_core.events.audit import FileAuditLog
from rosy_core.events.bus import EventBus
from rosy_core.identity import RobotIdentity
from rosy_core.maps import MapSnapshotStore
from rosy_core.navigation.manager import NavigationManager
from rosy_core.navigation.swarm import SwarmManager
from rosy_core.power.battery import (
    BatteryConfig,
    BatteryCurve,
    BatteryMonitor,
)
from rosy_core.power.manager import (
    LidarPolicy,
    PowerConfig,
    PowerManager,
    PresenceConfig,
)
from rosy_core.profile import RobotProfile
from rosy_core.safety.manager import BatteryPolicy, SafetyManager, SpeedLimits
from rosy_core.state.manager import StateManager
from rosy_core.system.runtime import HostRuntimeProbe
from rosy_core.waypoints.manager import WaypointManager


#: 셧다운 요청 표식. 명령이 아니라 관찰이며, 판단과 실행은 호스트 유닛이 한다.
SHUTDOWN_SENTINEL_NAME = "battery-shutdown-request.json"


def _battery_config(raw: dict[str, Any], data_path: Any = None) -> BatteryConfig:
    """rosy_default.yaml의 safety 블록 → BatteryConfig (누락 키는 기본값 유지).

    곡선이 없거나 무효하면 기존 two-point 스팬으로 되돌아간다. 설정 오타 하나로
    로봇이 아예 뜨지 않는 것보다 정확도가 낮은 채로 도는 편이 낫다.
    """
    defaults = BatteryConfig()

    full = float(raw.get("battery_full_voltage", 8.4))
    empty = float(raw.get("battery_empty_voltage", 6.4))

    curve: BatteryCurve
    points = raw.get("battery_curve")
    try:
        if points:
            curve = BatteryCurve([(float(v), float(p)) for v, p in points])
        else:
            curve = BatteryCurve.from_span(full=full, empty=empty)
    except (ValueError, TypeError):
        try:
            curve = BatteryCurve.from_span(full=full, empty=empty)
        except ValueError:
            curve = BatteryCurve.default()

    sentinel = None if data_path is None else Path(data_path) / SHUTDOWN_SENTINEL_NAME

    return BatteryConfig(
        curve=curve,
        filter_tau_s=float(raw.get("battery_filter_tau_s", defaults.filter_tau_s)),
        warning_percent=float(raw.get("battery_warning_percent", defaults.warning_percent)),
        critical_percent=float(raw.get("battery_critical_percent", defaults.critical_percent)),
        deep_percent=float(raw.get("battery_deep_percent", defaults.deep_percent)),
        enter_samples=int(raw.get("battery_enter_samples", defaults.enter_samples)),
        exit_samples=int(raw.get("battery_exit_samples", defaults.exit_samples)),
        hysteresis_percent=float(
            raw.get("battery_hysteresis_percent", defaults.hysteresis_percent)),
        deep_dwell_s=float(raw.get("battery_deep_dwell_s", defaults.deep_dwell_s)),
        sentinel_path=sentinel,
        shutdown_grace_s=float(
            raw.get("battery_shutdown_grace_s", defaults.shutdown_grace_s)),
    )


def _power_config(raw: dict[str, Any]) -> PowerConfig:
    """rosy_default.yaml의 power 블록 → PowerConfig (누락 키는 기본값 유지)."""
    presence_raw = raw.get("presence", {}) or {}
    lidar_raw = raw.get("lidar", {}) or {}
    defaults, presence_defaults = PowerConfig(), PresenceConfig()
    lidar_defaults = LidarPolicy()
    lidar = LidarPolicy(
        standby_stop=bool(lidar_raw.get("standby_stop", lidar_defaults.standby_stop)),
        spinup_s=float(lidar_raw.get("spinup_s", lidar_defaults.spinup_s)),
    )
    presence = PresenceConfig(
        near_m=float(presence_raw.get("near_m", presence_defaults.near_m)),
        contact_m=float(presence_raw.get("contact_m", presence_defaults.contact_m)),
        hysteresis_m=float(presence_raw.get("hysteresis_m", presence_defaults.hysteresis_m)),
        detect_samples=int(presence_raw.get("detect_samples", presence_defaults.detect_samples)),
        release_samples=int(presence_raw.get("release_samples", presence_defaults.release_samples)),
        min_valid_m=float(presence_raw.get("min_valid_m", presence_defaults.min_valid_m)),
        max_valid_m=float(presence_raw.get("max_valid_m", presence_defaults.max_valid_m)),
    )
    return PowerConfig(
        enabled=bool(raw.get("enabled", defaults.enabled)),
        idle_after_s=float(raw.get("idle_after_s", defaults.idle_after_s)),
        standby_after_s=float(raw.get("standby_after_s", defaults.standby_after_s)),
        info_hold_s=float(raw.get("info_hold_s", defaults.info_hold_s)),
        active_rate_hz=float(raw.get("active_rate_hz", defaults.active_rate_hz)),
        idle_rate_hz=float(raw.get("idle_rate_hz", defaults.idle_rate_hz)),
        standby_rate_hz=float(raw.get("standby_rate_hz", defaults.standby_rate_hz)),
        presence=presence,
        lidar=lidar,
    )


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
    power: PowerManager
    battery: BatteryMonitor
    docking: DockingManager
    swarm: SwarmManager
    runtime_probe: HostRuntimeProbe
    maps: MapSnapshotStore
    audit: FileAuditLog
    started_at: float = field(default_factory=time.time)
    # Optional absorbed Control worker, owned by the RosyCoreNode lifecycle.
    # It is populated only when the explicit sensor adapter profile is enabled.
    control_adapter: Any = field(default=None, repr=False)

    @classmethod
    def build(cls, config: dict[str, Any], profile: RobotProfile,
              capability_data: dict, waypoints_path) -> "CoreServices":
        robot_id = config.get("robot", {}).get("id", "rosy_01")
        events = EventBus(robot_id, buffer_size=int(config.get("events", {}).get("ring_buffer_size", 1000)))
        audit = FileAuditLog(Path(waypoints_path).parent / "audit.jsonl")
        events.subscribe(audit.record)

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
                               events=events, policy_required=safety_cfg.get('control_policy_required', False))

        identity = RobotIdentity.from_config(config, profile_model=profile.model)
        capability = Capability(capability_data)
        state = StateManager(robot_id)
        registry = SourceRegistry(config.get("command_sources"))
        modes = ModeMachine()
        command = CommandManager(registry, modes, safety, events=events)
        waypoints = WaypointManager(waypoints_path, events=events)
        nav = NavigationManager(events, state, waypoints, safety,
                                stuck_timeout_s=float(safety_cfg.get("stuck_timeout_s", 30.0)))
        power = PowerManager(_power_config(config.get("power", {})), events=events)
        battery = BatteryMonitor(
            _battery_config(safety_cfg, data_path=waypoints_path.parent),
            events=events)
        docking = DockingManager(
            database=DockDatabase(waypoints_path.parent / "docks.json"),
            safety=safety,
            config=DockingConfig(),
            events=events,
            # 검출기는 경계 뒤다 — 실물 선택은 카메라 스펙 뒤로 유보되어 있고,
            # ros_bridge 가 기종에 맞는 것을 주입한다.
            detector_factory=lambda dock, dock_type: SimulatedDetector(script=[]),
            agent_factory=lambda dock: DockAgent(dock.agent_url),
            capability_provider=lambda: capability.supports("docking.supported"),
            map_id_provider=lambda: state.map_id,
            battery=battery,
        )
        swarm = SwarmManager(
            events, state, nav, safety, capability,
            # Nav2 를 두고 다투는 것은 DOCKING/UNDOCKING 뿐이다. DOCKED·CHARGING 은
            # 주차 상태이고, DOCK_FAILED 는 설계상 종착이라 그것으로 막으면
            # 도킹 실패 한 번이 군집을 영구히 비활성화한다.
            docking_active_provider=lambda: docking.state in (
                DockState.DOCKING, DockState.UNDOCKING),
            map_id_provider=lambda: state.map_id,
        )
        nav.session_closed_listener = swarm.on_navigation_session_closed
        def reflect_stop():
            state.set_estop(True)
        safety.estop_listeners.append(reflect_stop)
        safety.estop_listeners.append(swarm.on_estop)
        safety.estop_listeners.append(lambda: nav.cancel(source='safety_manager'))
        runtime_probe = HostRuntimeProbe(
            host_root=os.environ.get("ROSY_HOST_ROOT", "/"),
            data_path=waypoints_path.parent,
        )
        return cls(config=config, identity=identity, profile=profile, capability=capability,
                   events=events, state=state, registry=registry, modes=modes,
                   command=command, safety=safety, waypoints=waypoints, nav=nav,
                   power=power, battery=battery, docking=docking, swarm=swarm,
                   runtime_probe=runtime_probe, maps=MapSnapshotStore(),
                   audit=audit)
