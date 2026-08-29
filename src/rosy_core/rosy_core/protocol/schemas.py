"""rosy_core.protocol.schemas — Fleet 프로토콜 envelope/이벤트 스키마 (P1-19, ADR-D-10).

계약 원천: ROSY-API-REF-001 §6~§9.
- Envelope: 모든 Fleet↔Robot WS 메시지 공통 포장 (API Ref §7.1)
- HelloPayload / WelcomePayload: 핸드셰이크 (API Ref §7.2)
- HeartbeatPayload: 1 Hz 상태 전송 (API Ref §7.3)
- EventMessage: EVT-001 이벤트 모델 (API Ref §8)
- AckPayload: 명령 추적 (API Ref §7.5, PRT-004)

스키마 변경은 추가 전용(Additive)만 허용 — protocol_version MINOR 상향 (PRT-006).
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

PROTOCOL_VERSION = "1.0"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def new_msg_id() -> str:
    return str(uuid4())


# --- 공용 enum (API Ref §4) ----------------------------------------------

class RobotMode(str, enum.Enum):
    IDLE = "IDLE"
    MANUAL = "MANUAL"
    NAVIGATION = "NAVIGATION"
    DOCKING = "DOCKING"
    EMERGENCY = "EMERGENCY"


class NavigationState(str, enum.Enum):
    IDLE = "IDLE"
    PLANNING = "PLANNING"
    NAVIGATING = "NAVIGATING"
    ARRIVED = "ARRIVED"
    CANCELED = "CANCELED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class HealthState(str, enum.Enum):
    OK = "OK"
    WARNING = "WARNING"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"


class Severity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AckStatus(str, enum.Enum):
    ACCEPTED = "ACCEPTED"
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# --- Envelope (API Ref §7.1, PRT-001) ------------------------------------

class EnvelopeType(str, enum.Enum):
    HELLO = "hello"
    WELCOME = "welcome"
    HEARTBEAT = "heartbeat"
    EVENT = "event"
    COMMAND = "command"
    ACK = "ack"
    ERROR = "error"


class Envelope(BaseModel):
    protocol_version: str = PROTOCOL_VERSION
    msg_id: str = Field(default_factory=new_msg_id)
    correlation_id: Optional[str] = None
    type: EnvelopeType
    ts: str = Field(default_factory=utc_now_iso)
    payload: dict[str, Any] = Field(default_factory=dict)


# --- 핸드셰이크 (API Ref §7.2, PRT-002) -----------------------------------

class HelloPayload(BaseModel):
    robot_id: str
    pairing_token: str
    api_versions: list[str] = ["v1"]
    protocol_version: str = PROTOCOL_VERSION


class WelcomePayload(BaseModel):
    robot_id: str
    fleet_name: str
    long_term_token: Optional[str] = None
    protocol_version: str = PROTOCOL_VERSION


# --- Heartbeat (API Ref §7.3, PRT-003) ------------------------------------

class Pose(BaseModel):
    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0


class Velocity(BaseModel):
    linear: float = 0.0
    angular: float = 0.0


class Battery(BaseModel):
    percent: float = 0.0
    voltage: Optional[float] = None


class SafetySummary(BaseModel):
    estop: bool = False


class StateSnapshot(BaseModel):
    """로봇 상태 스냅샷 — /ws/state payload와 동일 (API Ref §6.1)."""

    robot_id: str
    online: bool = True
    mode: RobotMode = RobotMode.IDLE
    navigation: NavigationState = NavigationState.IDLE
    map_id: Optional[str] = None
    pose: Pose = Field(default_factory=Pose)
    velocity: Velocity = Field(default_factory=Velocity)
    battery: Battery = Field(default_factory=Battery)
    safety: SafetySummary = Field(default_factory=SafetySummary)
    diagnostics_summary: dict[str, HealthState] = Field(default_factory=dict)
    seq: int = 0
    timestamp: str = Field(default_factory=utc_now_iso)


class HeartbeatPayload(BaseModel):
    state_snapshot: StateSnapshot


# --- 이벤트 (EVT-001, API Ref §8 이벤트 카탈로그) ---------------------------

class EventMessage(BaseModel):
    seq: int
    event_id: str = Field(default_factory=new_msg_id)
    ts: str = Field(default_factory=utc_now_iso)
    robot_id: str
    type: str                      # 예: "nav.completed" — 카탈로그는 API Ref §8
    severity: Severity = Severity.INFO
    source: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


# --- 명령 추적 (API Ref §7.5, PRT-004) --------------------------------------

class AckPayload(BaseModel):
    status: AckStatus
    error: Optional[str] = None
