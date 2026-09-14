# Site Middleware Role Fabric Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** D-59 역할 경계를 호스트 시험으로 잠그고, 관제 PC 쪽 `SiteHub`가 로봇 envelope를 모으고 REST 원자 액션만 흩뿌리게 한다. 로봇에 브로커를 올리지 않고, `FleetAgent`는 계속 끈다.

**Architecture:** 사이트 오케스트레이터는 `src/rosy_fleet/rosy_fleet/hub/`에 산다. CORE·IO·인지·Nav2는 수정하지 않는다. Hub는 `rosy_core.protocol.schemas`만 import한다(D-18). 모음은 `Envelope` hello/heartbeat/event, 흩뿌림은 기존 `RobotClient` REST(`POST /api/v1/safety/stop` 등)다. pose 팬아웃은 이미 있는 `Relay`가 하고 Hub가 합성하지 않는다. 설계: `docs/plans/2026-09-14-site-middleware-role-fabric-design.md`.

**Tech Stack:** Python 3.12, pydantic 스키마, pytest(ROS 없음), 기존 httpx `RobotClient` 프로토콜, FakeRobot. 새 네트워크 데몬·웹 UI·영상 경로 없음.

**이 계획이 아닌 것:** 관제 UI, 미션 DSL, `FleetAgent` outbound 소켓, `rmw_zenoh`, Kafka/NATS/MQTT, L3 영상 분리, ARM64/Pi Device GO. 그것들은 후속 계획이다.

**Windows:** 저장소 `Rosy OS` 루트에서 `python -m pytest` — `src/rosy_fleet/test/conftest.py`가 `sys.path`를 잡는다. 루트 `test/`는 기존 `robot_contracts`를 쓴다.

**커밋:** `type(scope): 무엇을 왜` 한 줄 + 본문.

---

## File Structure

| 파일 | 책임 |
|---|---|
| `test/test_site_fabric_roles.py` | 로봇 compose에 브로커 금지, 인지 소스가 `cmd_vel`을 안 만듦 |
| `src/rosy_fleet/test/test_boundaries.py` | 패키지 전체 `rclpy` 금지, hub는 `rosy_core.protocol.schemas`만 |
| `src/rosy_core/test/test_fleet_agent.py` | outbound 계속 꺼짐 (기존 + 핀) |
| `src/rosy_fleet/rosy_fleet/hub/__init__.py` | 패키지 마커 |
| `src/rosy_fleet/rosy_fleet/hub/registry.py` | 로봇 기록(스냅샷·이벤트 seq). 순수, 전송 없음 |
| `src/rosy_fleet/rosy_fleet/hub/hub.py` | hello/welcome, gather, role 거절, scatter_estop |
| `src/rosy_fleet/test/test_hub.py` | Hub 계약 시험 |
| `src/rosy_fleet/rosy_fleet/swarm/transport.py` | `RobotClient.estop()` REST |
| `src/rosy_fleet/test/fakes.py` | `FakeRobot.estop` |
| `src/rosy_fleet/AGENTS.md`, `src/rosy_fleet/test/AGENTS.md`, `docs/plans/AGENTS.md` | 인덱스 |

---

### Task 1: 로봇 compose는 사이트 브로커가 아니다

**Files:**
- Create: `test/test_site_fabric_roles.py`
- Modify: 없음. `deploy/robot/compose.yaml`은 지금 세 서비스라 테스트가 초록이어야 한다.

- [ ] **Step 1: 실패하는 테스트**

`test/test_site_fabric_roles.py`:

```python
"""D-59: 로봇 런타임은 사이트 버스가 아니다. 브로커·인지 cmd_vel 금지."""

from pathlib import Path

from robot_contracts import ROOT, compose

_BROKER_TOKENS = (
    "kafka", "nats", "mqtt", "rabbitmq", "redis", "pulsar", "redpanda", "zenoh-router",
)


def test_robot_compose_has_no_site_broker_service():
    services = compose()["services"]
    assert set(services) == {"rosy-core", "rosy-motor", "rosy-io"}
    blob = (ROOT / "deploy" / "robot" / "compose.yaml").read_text(encoding="utf-8").lower()
    for token in _BROKER_TOKENS:
        assert token not in blob, token


def test_perception_sources_do_not_publish_cmd_vel():
    roots = [
        ROOT / "src" / "rosy_control" / "rosy_control" / "sensing" / "camera_worker.py",
        ROOT / "src" / "rosy_control" / "rosy_control" / "camera_detect_node.py",
    ]
    for path in roots:
        text = path.read_text(encoding="utf-8")
        assert "cmd_vel" not in text, path
        assert "create_publisher" not in text or "Twist" not in text
```

카메라 노드는 `create_publisher`가 있으므로 두 번째 assert는 `Twist` 부재로 잠근다. `cmd_vel` 부분 문자열만으로 `camera_worker.py`를 자른다.

- [ ] **Step 2: 실행해서 실패 확인**

Run: `python -m pytest test/test_site_fabric_roles.py -v`

Expected: FAIL — `ModuleNotFoundError`가 아니라 파일이 없음. 파일을 만든 뒤에는 통과해야 한다. 이 Task의 구현은 테스트 파일 자체가 가드다. compose를 바꾸지 마라.

- [ ] **Step 3: 통과 확인**

Run: `python -m pytest test/test_site_fabric_roles.py -v`

Expected: PASS (2 passed)

- [ ] **Step 4: Commit**

```bash
git add test/test_site_fabric_roles.py
git commit -m "test(fabric): pin robot compose and perception off the site bus"
```

---

### Task 2: rosy_fleet 전 패키지 역할 경계

**Files:**
- Modify: `src/rosy_fleet/test/test_boundaries.py`

- [ ] **Step 1: 실패하는 테스트 추가**

`test_boundaries.py` 하단에:

```python
FLEET_PKG = Path(__file__).resolve().parents[1] / "rosy_fleet"
HUB_DIR = FLEET_PKG / "hub"
CORE_FORBIDDEN_PREFIXES = (
    "rclpy",
    "rosy_core.command",
    "rosy_core.bridge",
    "rosy_core.safety",
    "rosy_core.navigation",
    "rosy_core.api",
)


def _py_files(root: Path):
    return sorted(p for p in root.rglob("*.py") if p.name != "__pycache__")


def test_fleet_package_never_imports_rclpy():
    for path in _py_files(FLEET_PKG):
        for name in _imports(path):
            assert name != "rclpy" and not name.startswith("rclpy."), f"{path.name} imports {name}"


def test_hub_may_import_only_protocol_schemas_from_rosy_core():
    if not HUB_DIR.exists():
        pytest.fail("hub package missing — Task 4 creates it; this test should fail until then")
    for path in _py_files(HUB_DIR):
        for name in _imports(path):
            if name == "rosy_core" or name.startswith("rosy_core."):
                assert name == "rosy_core.protocol.schemas", f"{path.name} imports {name}"
            for banned in CORE_FORBIDDEN_PREFIXES:
                assert name != banned and not name.startswith(banned + "."), path.name
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `python -m pytest src/rosy_fleet/test/test_boundaries.py::test_hub_may_import_only_protocol_schemas_from_rosy_core -v`

Expected: FAIL — `hub package missing`

`test_fleet_package_never_imports_rclpy`는 지금 트리에서 PASS여야 한다.

- [ ] **Step 3: hub 패키지 마커만 만들어 경계 시험을 초록으로**

Create `src/rosy_fleet/rosy_fleet/hub/__init__.py` (빈 파일 또는 한 줄 docstring).

`test_hub_may_import_only_protocol_schemas_from_rosy_core`가 빈 패키지에서 PASS가 된다. 구현 모듈은 Task 4에서 추가한다.

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest src/rosy_fleet/test/test_boundaries.py -v`

Expected: PASS (기존 formation/arming + 새 2개)

- [ ] **Step 5: Commit**

```bash
git add src/rosy_fleet/test/test_boundaries.py src/rosy_fleet/rosy_fleet/hub/__init__.py
git commit -m "test(fleet): lock hub and package off rclpy and CORE internals"
```

---

### Task 3: FleetAgent는 이 슬라이스에서 열리지 않는다

**Files:**
- Modify: `src/rosy_core/test/test_fleet_agent.py` (핀만 추가, agent 구현 금지)

- [ ] **Step 1: 실패하지 말아야 할 핀**

기존 두 테스트에 더해:

```python
def test_connect_raises_until_a_later_plan_enables_outbound():
    agent = FleetAgent()
    try:
        agent._connect("wss://fleet.example/ws/robots")
    except RuntimeError as exc:
        assert "not enabled" in str(exc)
    else:
        raise AssertionError("outbound must stay disabled in this slice")
```

- [ ] **Step 2: 실행**

Run: `python -m pytest src/rosy_core/test/test_fleet_agent.py -v`

Expected: PASS. `_connect`를 구현하거나 `start()`에서 부르지 마라.

- [ ] **Step 3: Commit**

```bash
git add src/rosy_core/test/test_fleet_agent.py
git commit -m "test(core): keep FleetAgent outbound disabled for the hub slice"
```

---

### Task 4: Registry와 hello/welcome

**Files:**
- Create: `src/rosy_fleet/rosy_fleet/hub/registry.py`
- Create: `src/rosy_fleet/rosy_fleet/hub/hub.py`
- Create: `src/rosy_fleet/test/test_hub.py`

- [ ] **Step 1: 실패하는 테스트**

`src/rosy_fleet/test/test_hub.py`:

```python
"""SiteHub는 계약 envelope만 모은다. 바퀴 속도와 원본 영상은 거절한다 (D-59)."""

from rosy_core.protocol.schemas import (
    Envelope,
    EnvelopeType,
    EventMessage,
    HeartbeatPayload,
    HelloPayload,
    StateSnapshot,
)
from rosy_fleet.swarm.robots import RobotEndpoint
from rosy_fleet.hub.hub import SiteHub


def _ep(robot_id: str = "rosy_01") -> RobotEndpoint:
    return RobotEndpoint(robot_id, "http://127.0.0.1:8080", "pair-01")


def _hello(robot_id="rosy_01", token="pair-01") -> Envelope:
    payload = HelloPayload(robot_id=robot_id, pairing_token=token).model_dump()
    return Envelope(type=EnvelopeType.HELLO, payload=payload)


def test_hello_with_known_token_is_welcomed_and_listed_online():
    hub = SiteHub([_ep()])
    reply = hub.handle(_hello())
    assert reply.type is EnvelopeType.WELCOME
    assert reply.payload["robot_id"] == "rosy_01"
    assert hub.registry.online_ids() == ["rosy_01"]


def test_hello_with_wrong_token_is_pairing_invalid_and_stays_offline():
    hub = SiteHub([_ep()])
    reply = hub.handle(_hello(token="nope"))
    assert reply.type is EnvelopeType.ERROR
    assert reply.payload["code"] == "PAIRING_INVALID"
    assert hub.registry.online_ids() == []
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `python -m pytest src/rosy_fleet/test/test_hub.py -v`

Expected: FAIL — `ModuleNotFoundError: rosy_fleet.hub.hub`

- [ ] **Step 3: 최소 구현**

`registry.py`:

```python
"""로봇 기록. 전송·ROS 없음."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from rosy_core.protocol.schemas import EventMessage, StateSnapshot


@dataclass
class RobotRecord:
    robot_id: str
    online: bool = False
    snapshot: Optional[StateSnapshot] = None
    last_event_seq: int = 0
    events: list[EventMessage] = field(default_factory=list)


class RobotRegistry:
    def __init__(self) -> None:
        self._robots: dict[str, RobotRecord] = {}

    def record(self, robot_id: str) -> RobotRecord:
        row = self._robots.get(robot_id)
        if row is None:
            row = RobotRecord(robot_id=robot_id)
            self._robots[robot_id] = row
        return row

    def online_ids(self) -> list[str]:
        return sorted(r.robot_id for r in self._robots.values() if r.online)
```

`hub.py` (hello만):

```python
"""관제 쪽 모음/흩뿌림. 최종 cmd_vel과 Image를 다루지 않는다 (D-59)."""

from __future__ import annotations

from typing import Optional, Sequence

from rosy_core.protocol.schemas import (
    Envelope,
    EnvelopeType,
    HelloPayload,
    WelcomePayload,
)
from rosy_fleet.hub.registry import RobotRegistry
from rosy_fleet.swarm.robots import RobotEndpoint
from rosy_fleet.swarm.transport import RobotClient


def _error(code: str, message: str) -> Envelope:
    return Envelope(type=EnvelopeType.ERROR, payload={"code": code, "message": message})


class SiteHub:
    def __init__(
        self,
        endpoints: Sequence[RobotEndpoint],
        clients: Optional[dict[str, RobotClient]] = None,
        fleet_name: str = "rosy-site",
    ) -> None:
        self._tokens = {e.robot_id: e.token for e in endpoints}
        self._clients = clients or {}
        self._paired: set[str] = set()
        self.registry = RobotRegistry()
        self._fleet_name = fleet_name

    def handle(self, envelope: Envelope) -> Envelope:
        if envelope.type is EnvelopeType.HELLO:
            return self._hello(envelope)
        return _error("SESSION_NOT_PAIRED", "hello first")

    def _hello(self, envelope: Envelope) -> Envelope:
        try:
            hello = HelloPayload.model_validate(envelope.payload)
        except Exception:
            return _error("PAIRING_INVALID", "bad hello")
        expected = self._tokens.get(hello.robot_id)
        if expected is None or expected != hello.pairing_token:
            return _error("PAIRING_INVALID", "unknown robot or token")
        row = self.registry.record(hello.robot_id)
        row.online = True
        self._paired.add(hello.robot_id)
        welcome = WelcomePayload(
            robot_id=hello.robot_id,
            fleet_name=self._fleet_name,
        )
        return Envelope(type=EnvelopeType.WELCOME, payload=welcome.model_dump())
```

`hub/__init__.py`는 구현을 재수출하지 않아도 된다. 테스트는 모듈 경로로 import한다.

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest src/rosy_fleet/test/test_hub.py src/rosy_fleet/test/test_boundaries.py -v`

Expected: PASS. hub가 `rosy_core.protocol.schemas`만 CORE에서 import하는지 경계 시험이 확인한다.

- [ ] **Step 5: Commit**

```bash
git add src/rosy_fleet/rosy_fleet/hub src/rosy_fleet/test/test_hub.py
git commit -m "feat(fleet): welcome paired robots on the site hub"
```

---

### Task 5: heartbeat와 이벤트를 모은다

**Files:**
- Modify: `src/rosy_fleet/rosy_fleet/hub/hub.py`
- Modify: `src/rosy_fleet/rosy_fleet/hub/registry.py` (필요 시 `events_since`)
- Modify: `src/rosy_fleet/test/test_hub.py`

- [ ] **Step 1: 실패하는 테스트**

```python
def test_heartbeat_before_hello_is_rejected():
    hub = SiteHub([_ep()])
    snap = StateSnapshot(robot_id="rosy_01")
    env = Envelope(
        type=EnvelopeType.HEARTBEAT,
        payload=HeartbeatPayload(state_snapshot=snap).model_dump(mode="json"),
    )
    reply = hub.handle(env)
    assert reply.type is EnvelopeType.ERROR
    assert reply.payload["code"] == "SESSION_NOT_PAIRED"


def test_heartbeat_updates_registry_snapshot():
    hub = SiteHub([_ep()])
    hub.handle(_hello())
    snap = StateSnapshot(robot_id="rosy_01", seq=4)
    env = Envelope(
        type=EnvelopeType.HEARTBEAT,
        payload=HeartbeatPayload(state_snapshot=snap).model_dump(mode="json"),
    )
    reply = hub.handle(env)
    assert reply.type is EnvelopeType.WELCOME or reply.payload == {} or reply.type is EnvelopeType.HEARTBEAT
    stored = hub.registry.record("rosy_01").snapshot
    assert stored is not None
    assert stored.seq == 4


def test_events_are_kept_in_seq_order_and_gap_fill_reads_since_seq():
    hub = SiteHub([_ep()])
    hub.handle(_hello())
    for seq in (1, 2, 3):
        event = EventMessage(seq=seq, robot_id="rosy_01", type="nav.completed")
        hub.handle(Envelope(type=EnvelopeType.EVENT, payload=event.model_dump(mode="json")))
    filled = hub.registry.events_since("rosy_01", since_seq=1)
    assert [e.seq for e in filled] == [2, 3]
```

heartbeat 응답은 새 타입이 필요 없다. `handle`이 빈 payload의 같은 상관 envelope를 돌려주거나, 이벤트는 응답이 `{"accepted": true}` 정도면 된다. 테스트의 heartbeat 응답 단언은 **에러가 아님**으로 느슨하게 두고, 구현은 `Envelope(type=EnvelopeType.HEARTBEAT, payload={})`를 돌려라. 위 테스트 세 번째 assert를 구현에 맞춰 이렇게 바꿔라:

```python
    reply = hub.handle(env)
    assert reply.type is not EnvelopeType.ERROR
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `python -m pytest src/rosy_fleet/test/test_hub.py::test_heartbeat_updates_registry_snapshot -v`

Expected: FAIL — heartbeat가 `SESSION_NOT_PAIRED` 또는 AttributeError

- [ ] **Step 3: handle에 HEARTBEAT/EVENT 분기**

- HELLO가 아닌데 `robot_id`가 `_paired`에 없으면 `SESSION_NOT_PAIRED`.
- HEARTBEAT: `HeartbeatPayload.model_validate`, `row.snapshot = payload.state_snapshot`, 응답은 에러가 아닌 Envelope.
- EVENT: `EventMessage.model_validate(envelope.payload)`, `row.events.append`, `row.last_event_seq = max(...)`.
- `RobotRegistry.events_since(robot_id, since_seq)` → `seq > since_seq`인 이벤트.

이벤트 payload에 robot_id가 페어된 id와 다르면 `PAIRING_INVALID`.

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest src/rosy_fleet/test/test_hub.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/rosy_fleet/rosy_fleet/hub src/rosy_fleet/test/test_hub.py
git commit -m "feat(fleet): gather heartbeat and events on the site hub"
```

---

### Task 6: 역할 침범 envelope는 거절한다

**Files:**
- Modify: `src/rosy_fleet/rosy_fleet/hub/hub.py`
- Modify: `src/rosy_fleet/test/test_hub.py`

- [ ] **Step 1: 실패하는 테스트**

```python
def test_inbound_command_envelope_is_role_violation():
    hub = SiteHub([_ep()])
    hub.handle(_hello())
    reply = hub.handle(Envelope(type=EnvelopeType.COMMAND, payload={"twist": {"linear": 0.2}}))
    assert reply.type is EnvelopeType.ERROR
    assert reply.payload["code"] == "ROLE_VIOLATION"


def test_payload_with_cmd_vel_or_image_is_role_violation():
    hub = SiteHub([_ep()])
    hub.handle(_hello())
    for payload in ({"cmd_vel": {"linear": 0.1}}, {"image": "base64"}, {"Image": True}):
        reply = hub.handle(Envelope(type=EnvelopeType.EVENT, payload=payload))
        assert reply.payload["code"] == "ROLE_VIOLATION", payload


def test_peer_source_is_rejected_on_follow_scatter_params():
    """D-31: peer 소스는 계약에 있지만 허브는 거절한다."""
    from rosy_core.protocol.schemas import SwarmFollowParams, SwarmReferenceSource

    params = SwarmFollowParams(
        target_robot_id="rosy_01",
        source=SwarmReferenceSource.PEER,
    )
    hub = SiteHub([_ep()])
    try:
        hub.assert_scatterable(params)
    except Exception as exc:
        assert getattr(exc, "code", None) == "ROLE_VIOLATION" or "peer" in str(exc).lower()
    else:
        raise AssertionError("peer follow must not scatter")
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `python -m pytest src/rosy_fleet/test/test_hub.py::test_inbound_command_envelope_is_role_violation -v`

Expected: FAIL

- [ ] **Step 3: 구현**

`handle` 맨 앞(HELLO 제외 후):

- `envelope.type is COMMAND` → `ROLE_VIOLATION` ("robots do not command the hub").
- payload 키를 소문자로 봐 `cmd_vel`, `image`, `twist`가 있으면 거절. EVENT의 정상 필드는 EventMessage에 있으므로 이 키는 없다.
- `assert_scatterable(params)`: `params.source is SwarmReferenceSource.PEER`이면 `HubError("ROLE_VIOLATION", ...)`.

```python
class HubError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest src/rosy_fleet/test/test_hub.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/rosy_fleet/rosy_fleet/hub/hub.py src/rosy_fleet/test/test_hub.py
git commit -m "feat(fleet): reject command, image, and peer envelopes on the hub"
```

---

### Task 7: 흩뿌림은 safety/stop REST다

**Files:**
- Modify: `src/rosy_fleet/rosy_fleet/swarm/transport.py` (`RobotClient` + `HttpRobotClient.estop`)
- Modify: `src/rosy_fleet/test/fakes.py` (`FakeRobot.estop`)
- Modify: `src/rosy_fleet/rosy_fleet/hub/hub.py` (`async scatter_estop`)
- Modify: `src/rosy_fleet/test/test_hub.py`
- Modify: `src/rosy_fleet/test/test_transport.py`에 Http 경로 핀이 있으면 한 케이스 추가

`HttpRobotClient`의 `_post`를 재사용한다.

```python
async def estop(self) -> dict:
    return await self._post("/api/v1/safety/stop")
```

`RobotClient` Protocol에 `async def estop(self) -> dict: ...`를 추가한다. Protocol을 만족하는 FakeRobot에:

```python
async def estop(self) -> dict:
    self.calls.append(("estop",))
    self.log.append((self.robot_id, "estop"))
    return {"estop": True}
```

- [ ] **Step 1: 실패하는 테스트**

```python
from fakes import FakeRobot, run


def test_scatter_estop_calls_robot_rest_not_a_twist():
    async def main():
        robot = FakeRobot("rosy_01")
        hub = SiteHub([_ep()], clients={"rosy_01": robot})
        hub.handle(_hello())
        result = await hub.scatter_estop("rosy_01")
        assert result == {"estop": True}
        assert robot.calls == [("estop",)]
        assert not any("cmd_vel" in str(c) or "twist" in str(c).lower() for c in robot.calls)

    run(main())


def test_scatter_estop_unknown_robot_errors():
    async def main():
        hub = SiteHub([_ep()])
        try:
            await hub.scatter_estop("rosy_99")
        except Exception as exc:
            assert "rosy_99" in str(exc) or getattr(exc, "code", "") == "UNKNOWN_ROBOT"
        else:
            raise AssertionError("missing client must fail")

    run(main())
```

- [ ] **Step 2: 실행해서 실패 확인**

Run: `python -m pytest src/rosy_fleet/test/test_hub.py::test_scatter_estop_calls_robot_rest_not_a_twist -v`

Expected: FAIL — `estop` 없음

- [ ] **Step 3: 구현**

`SiteHub.scatter_estop`:

```python
async def scatter_estop(self, robot_id: str) -> dict:
    client = self._clients.get(robot_id)
    if client is None:
        raise HubError("UNKNOWN_ROBOT", robot_id)
    return await client.estop()
```

Http 클라이언트의 경로 문자열이 `/api/v1/safety/stop`인지 `test_transport.py`에 한 줄 핀을 추가할 수 있다. 네트워크 없이 소스 문자열이 있는지로 잠그려면:

```python
def test_http_estop_posts_safety_stop():
    import inspect
    from rosy_fleet.swarm.transport import HttpRobotClient
    src = inspect.getsource(HttpRobotClient.estop)
    assert "/api/v1/safety/stop" in src
```

이 핀은 twist 경로가 섞이는 것을 막는다.

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest src/rosy_fleet/test/test_hub.py src/rosy_fleet/test/test_transport.py src/rosy_fleet/test/test_session.py src/rosy_fleet/test/test_relay.py -v`

Expected: PASS. FakeRobot에 `estop`이 빠져 Protocol 구조적 검사가 있으면 함께 고친다. 기존 세션 테스트가 `estop`을 부르지 않아도 FakeRobot은 메서드를 가져야 한다.

- [ ] **Step 5: Commit**

```bash
git add src/rosy_fleet/rosy_fleet/swarm/transport.py src/rosy_fleet/test/fakes.py src/rosy_fleet/rosy_fleet/hub/hub.py src/rosy_fleet/test/test_hub.py src/rosy_fleet/test/test_transport.py
git commit -m "feat(fleet): scatter e-stop through robot REST only"
```

---

### Task 8: 회귀 — 로컬 우선과 릴레이 0 Hz는 그대로다

**Files:**
- Modify: 없음 (명령만). 깨지면 Task 4–7 구현을 되돌릴 것. CORE에 hub import를 넣지 마라.

- [ ] **Step 1: 실행**

```powershell
python -m pytest src/rosy_fleet/test src/rosy_core/test/test_fleet_agent.py test/test_site_fabric_roles.py test/test_robot_runtime.py -q
```

Expected: 기존 실패 없이 PASS. `test_robot_runtime.py`의 서비스 집합 `{rosy-core, rosy-motor, rosy-io}`가 여전히 맞다.

- [ ] **Step 2: 인덱스**

`src/rosy_fleet/AGENTS.md` Key Files에 `rosy_fleet/hub/hub.py`, `hub/registry.py`를 한 줄씩 추가. Purpose에 “SiteHub는 계약 gather/scatter이며 ROS가 없다. Fleet 서버 UI가 아니다.”

`src/rosy_fleet/test/AGENTS.md`에 `test_hub.py` 행 추가.

`src/rosy_fleet/rosy_fleet/hub/AGENTS.md`를 만든다:

```markdown
<!-- Parent: ../AGENTS.md -->
# hub

## Purpose

D-59 SiteHub: hello/heartbeat/event gather, REST scatter. No rclpy, no cmd_vel, no Image.

## Key Files

| File | Description |
|---|---|
| `registry.py` | Online snapshot and event seq |
| `hub.py` | Envelope handle + scatter_estop |

## Testing Requirements

`src/rosy_fleet/test/test_hub.py`, `test_boundaries.py`
```

- [ ] **Step 3: Commit**

```bash
git add src/rosy_fleet/AGENTS.md src/rosy_fleet/test/AGENTS.md src/rosy_fleet/rosy_fleet/hub/AGENTS.md
git commit -m "docs(fleet): index the site hub role boundary"
```

---

### Task 9: 설계 문서에 이 슬라이스 완료 조건을 연결

**Files:**
- Modify: `docs/plans/2026-09-14-site-middleware-role-fabric-design.md` §7 항목 2를 이 계획 파일로 링크
- Modify: `docs/plans/AGENTS.md` (execute 계획 행)

완료 조건(이 Task에서 코드 없음):

- `test_site_fabric_roles.py` PASS
- `test_hub.py` PASS
- `test_boundaries.py` PASS
- `test_fleet_agent.py` PASS
- compose 서비스 집합 불변

후속 계획으로만 남길 것(이 파일 끝에 한 절):

1. `rosy_fleet hub --listen` WebSocket 서버 (실제 관제 PC 프로세스)
2. CORE `FleetAgent` outbound — listen이 있고 설정이 켜질 때만
3. 관제 UI는 Hub REST/상태만
4. 영상 L3 분리 (D-41/D-52)
5. Device ARTIFACT/Pi는 기존 2026-09-13 계획

- [ ] **Step 1: 문서만 수정하고 시험은 Task 8 명령을 한 번 더**

- [ ] **Step 2: Commit**

```bash
git add docs/plans/2026-09-14-site-middleware-role-fabric-design.md docs/plans/AGENTS.md docs/plans/2026-09-14-site-middleware-role-fabric.md
git commit -m "docs(fabric): record hub-slice completion gates and sequels"
```

---

## 완료 판정

이 계획이 끝난 상태:

- 디바이스는 미들웨어 **계약**으로만 허브에 모인다 (hello/heartbeat/event).
- 허브는 e-stop을 **REST**로만 흩뿌린다.
- 로봇 compose·인지·FleetAgent·단일 cmd_vel 경계는 시험이 지킨다.
- 관제 UI·영상·실제 listen 소켓·Pi 서명은 아직 없다. 그렇게 보고한다.

## 후속 계획 (이 슬라이스 밖)

1. `rosy_fleet hub --listen` WebSocket 서버 (실제 관제 PC 프로세스)
2. CORE `FleetAgent` outbound — listen이 있고 설정이 켜질 때만
3. 관제 UI는 Hub REST/상태만
4. 영상 L3 분리 (D-41/D-52)
5. Device ARTIFACT/Pi는 기존 2026-09-13 계획
