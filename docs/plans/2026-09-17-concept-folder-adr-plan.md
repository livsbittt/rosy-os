# Concept 폴더 → 미들웨어 ADR 계획

작성일: 2026-09-17
상태: D-65 Accepted로 올리고 D-67–D-71을 기록한다. 09–12·apt/`rosyctl`은 구현하지 않는다.

관련: D-1, D-11, D-12, D-32, D-38, D-55, D-57, D-62–D-66 ·
[docs/concept](../concept/README.md) ·
[CONCEPTS.md](../../CONCEPTS.md) ·
[concept-runtime-alignment](2026-09-16-concept-runtime-alignment-design.md) ·
[native Pi ARTIFACT](2026-09-17-arm64-artifact-native-pi-plan.md)

## 1. Goal

`docs/concept/00`–`15`를 **목표 OS**로 두고, 각 문서가 v1 미들웨어에서 무엇을 의미하는지 ADR로 고정한다. 이미 있는 결정(D-1, D-12, D-62, D-65, D-66)을 반복하지 않고, 비어 있던 경계를 채운다.

이 계획이 Fleet 서버, Pinky+OMX 합성, Compute Fabric, VLA, 데이터셋 파이프라인, `rosyctl`을 구현하지 않는다.

## 2. 문서 ↔ v1 ↔ ADR

| Concept | v1 의미 | ADR |
|---|---|---|
| 00 Vision | Ubuntu/ROS2 위 미들웨어. CORE SRS 제품 범위 | D-15, CORE SRS, D-65 |
| 01 Target architecture | v1 = CORE 프로세스 + D-62 슬라이스. Control Plane은 Fleet(미구현) | D-1, D-5, D-62, D-63, **D-71** |
| 02 Domain model | Node/Device/Component/Capability/Asset/Task → CORE 타입 | **D-65 Accepted** |
| 03 Runtime | `rosy_core` 단일 프로세스. `rosy-runtime-*` apt 패키지 없음 | D-1, D-62, **D-69** |
| 04 Device adapter | `rosy_bringup` / `rosy_omx_adapter` + YAML 매니페스트 | D-57, **D-69** |
| 05 ROS 2 interface | 외부 API는 REST/WS. `/rosy/{device_id}/…` 토픽 트리는 공개 API가 아님 | CORE SRS §1.3, D-65, **D-71** |
| 06 Device state | `RobotMode`가 명령·안전 계약. `DeviceState`는 inventory 파생 | **D-67** |
| 07 Capability | CAP-001 = `GET /capabilities`. 개념 id·available = inventory | D-11, D-32, **D-68** |
| 08 Task & workflow | 로봇은 `TaskKind` 원자 액션. 워크플로/미션 상태머신은 Fleet | D-12, **D-70** |
| 09 Composite robot | 단일 Device Asset만. Pinky+OMX는 D-55가 켜질 때까지 없음 | D-55, **D-71** |
| 10 Compute fabric | Gram/RTX 패브릭 없음 | **D-71** |
| 11 AI & Physical AI | vision/ai 슬라이스 카탈로그만. 모델 레지스트리 없음 | D-41, D-62, **D-71** |
| 12 Dataset pipeline | Teach-Record-Train 없음 | **D-71** |
| 13 Migration | Phase 0–3 live. Phase 4–5 = D-71 | D-65, D-68, **D-71** |
| 14 Verification | Device 계획의 ARTIFACT/DEVICE/FIELD. concept 14의 Gram/합성 수락은 v1 아님 | Device 계획, **D-71** |
| 15 Modular install | D-62 슬라이스 + runtime-mode. apt/`rosyctl` 없음 | D-62, **D-69**, **D-71** |

## 3. 새 ADR 요약

전문은 [ADR 로그](../reference/ROSY%20ADR%20Log.md).

| ID | 결정 |
|---|---|
| D-65 | 개념 객체 매핑. inventory·매니페스트·Phase 3가 있어 **Accepted** |
| D-67 | `RobotMode`가 운용 계약. `DeviceState`는 inventory만 |
| D-68 | CAP-001 문서와 개념 descriptor를 분리. available은 DeviceState |
| D-69 | 어댑터는 트리 안 YAML. Debian `rosy-adapter-*` 없음 |
| D-70 | 로봇에 PENDING→SUCCEEDED 워크플로 엔진을 두지 않는다 |
| D-71 | 05 공개 토픽 트리, 09–12, 14 패브릭 수락, 15 apt는 목표 OS이지 v1이 아니다 |

## 4. 실행 순서 (미들웨어)

코드는 이 ADR을 어기는 방향으로 가지 않는다.

### Task 1 — 기록 (이 커밋)

ADR 표·본문, concept README 매핑 표, 이 계획.

### Task 2 — D-67 잔여: 기동 중 BOOTING

`inventory_from_config(..., booting=True)`는 있다. 라이브 `CoreServices.inventory()`가 스냅샷 전에 BOOTING을 넘기도록 연결한다. `RobotMode` 값은 바꾸지 않는다.

### Task 3 — D-68 잔여 (선택)

`TaskKind.require()`는 CAP-001 플래그로 501을 유지한다. concept `available=false`(SAFE_STOP 등)는 기존 safety/estop 경로가 거절한다. require()가 concept id를 말하게 바꾸는 것은 에러 본문 계약이므로 별도 실행.

### Task 4 — 하지 않음

- concept 09 합성 Asset, OMX 활성화 (D-55가 켜질 때까지)
- concept 10–12 패브릭·VLA·에피소드 스토어
- concept 15 `rosyctl` / apt 메타패키지
- `rosy_core`를 `rosy-runtime-base` 프로세스로 분리 (D-1)
- ARTIFACT GO (별도 [native Pi 계획](2026-09-17-arm64-artifact-native-pi-plan.md))

## 5. 수락

- ADR 로그에 D-67–D-71이 있고 D-65가 Accepted다.
- concept README 매핑 표가 위 표를 가리킨다.
- 새 코드가 `rosyctl`, 합성 Asset, `/rosy/{device_id}/state`를 외부 API로 추가하면 이 계획에 어긋난다.
