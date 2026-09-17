---
module: rosy_interfaces
logical_modules: [M02]
owner: 장치
last_verified: { commit: "uncommitted", date: 2026-09-15 }
gates:
  SOURCE:
    state: HOLD
    blocker: "repo test/ 전체를 검색했으나 srv 스키마(Emotion/SetLed/SetBrightness/SetLamp)의 필드·타입을 고정하는 host-runnable contract test가 없다(`src/rosy_core/test/test_bridge_timers.py`는 rosy_interfaces를 import stub 목록에만 넣는다). rosidl 생성 결과 확인은 colcon build가 필요"
  LOCAL:
    state: HOLD
    blocker: "패키지에 test/ 디렉터리가 없다(package.xml의 ament_lint_auto는 colcon test에서만 실행됨). rosidl 코드 생성 확인은 colcon build 필요"
  ROS-SIM:
    state: N/A
  ARTIFACT:
    state: HOLD
    blocker: "io 이미지에 포함된다(deploy/robot/Dockerfile `COPY src/rosy_interfaces`, `--packages-select`에 포함). 서명 manifest·OCI archive·immutable registry digest 발행 전"
  DEVICE:
    state: HOLD
    blocker: "Pi OS Lite bench Device의 install-pi.sh 설치, verify-pi.sh, device-readback.sh --json 증거 없음"
  FIELD:
    state: PARKED
adrs: []
plans:
  - docs/plans/2026-09-12-rosy-os-module-evaluation-maintenance-design.md
  - docs/plans/2026-09-13-rosy-os-device-validation-implementation-plan.md
  - docs/plans/2026-09-15-module-harness-design.md
---
## 지금 상태

- LED·lamp·brightness·LCD emotion용 custom ROS 2 서비스(rosidl 패키지): `Emotion.srv`, `SetLed.srv`, `SetBrightness.srv`, `SetLamp.srv`. `.srv` 변경 후 `colcon build --packages-select rosy_interfaces`와 의존 패키지 재빌드가 필요하다.
- 모듈 경로는 clean이지만 ARTIFACT 판정 근거인 `deploy/robot/Dockerfile`에 미커밋 WIP가 있어 `last_verified`는 `uncommitted`다.
- REST/Fleet 계약은 여기 없다 — pydantic 스키마는 `rosy_core.protocol.schemas`가 유일 소스다(AGENTS.md).
- `deploy/robot/Dockerfile`의 io-build 단계가 `rosy_interfaces`를 복사·빌드한다. 이 모듈은 device에 실제로 배포된다.

## 다음 gate

1. CI `Build (colcon)` 단계가 이미 `src` 전체(rosy_interfaces 포함)를 빌드한다. 초록 CI run의 `cd src && colcon build --packages-select rosy_interfaces` 결과를 LOCAL/SOURCE 증거로 기록하거나, srv 필드·타입을 고정하는 host 계약 시험을 추가한다.
2. 서명된 native ARM64 artifact 발행 후 Pi readback(ARTIFACT → DEVICE), deploy/rosy_core와 동일 체인.

## 현재 유효한 금지사항

- REST/Fleet 계약을 이 패키지에 넣지 않는다 — `rosy_core.protocol.schemas`가 단일 소스다.
- 하드웨어 노드가 소비하는 request/response 필드는 안정적으로 유지한다(rename은 소비자 전원 동시 갱신 필요).
