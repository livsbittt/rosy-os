---
module: core
logical_modules: [M03, M04, M06, M07, M11, M12, M13]
owner: CORE
last_verified: { commit: "uncommitted", date: 2026-09-21 }
gates:
  SOURCE:
    state: GO
    evidence: "모듈 경계·흡수 소유권 계약 시험 통과 (2026-09-15, core suite와 test/ suite)"
    cmd: "python3 -m pytest src/core/test/test_module_criteria.py test/test_control_absorption_package.py -q"
  LOCAL:
    state: GO
    evidence: "1005 passed, 11 skipped (2026-09-21 Windows). D-151 traffic policy, atomic command gate, stage/apply API와 dashboard 계약 포함; 실제 Chromium 정책 적용 흐름 1 passed"
    cmd: "PYTHONPATH=src/core:src python3 -m pytest src/core/test -q"
  ROS-SIM:
    state: HOLD
    blocker: "2026-09-13 실제 ROS 출력 시험 이후 미재실행. ROS 2 Jazzy 환경에서 현재 트리로 재실행 필요. 2026-09-20 Gazebo 시도에서 부팅 AttributeError(self.core_common — D-126 개명 잔재)를 기록했고 6ff2cb8 에서 수정 — 재실행 증거는 아직 없음(docs/validation/map-260905-update-v2-2026-09-20/result.md)"
  ARTIFACT:
    state: HOLD
    blocker: "ARM64 개발 후보만 존재. 서명 manifest와 immutable digest 발행 전"
  DEVICE:
    state: HOLD
    blocker: "Pi bench Device 설치와 device-readback.sh --json 증거 없음. G4 viewport·보정 상태기계 미실행"
  FIELD:
    state: PARKED
adrs: [D-1, D-2, D-8, D-18, D-23, D-32, D-38, D-42, D-47, D-58, D-60, D-72, D-75, D-77, D-82, D-119, D-121, D-122, D-123, D-124, D-144, D-151]
plans:
  - docs/plans/2026-09-06-module-split-criteria.md
  - docs/plans/2026-09-13-control-safety-boundary.md
  - docs/plans/2026-09-13-rosy-os-device-validation-implementation-plan.md
  - docs/plans/2026-09-15-navigation-swarm-split-design.md
  - docs/plans/2026-09-15-module-harness-design.md
  - docs/plans/2026-09-17-interface-design-implementation-design.md
  - docs/plans/2026-09-21-hardware-mapping-g5-design.md
  - docs/plans/2026-09-21-hardware-mapping-g5.md
  - docs/plans/2026-09-21-semantic-road-control-design.md
  - docs/plans/2026-09-21-semantic-road-control.md
---
## 지금 상태

- 외부 API의 유일한 gateway이고 최종 `cmd_vel`의 유일한 발행자다(D-2, D-38).
- 운용자 콘솔은 `/dashboard`다(D-77). 증거 4상태와 capability 4상태가 HOST 계약 시험으로 산다. G4 DEVICE는 HOLD.
- 흡수된 Control sensor adapter는 기본 비활성이다(D-47).
- 실물 구동 판정은 없다. 이동은 ARTIFACT/DEVICE 이후에만 승격한다.

## 다음 gate

1. ROS Jazzy container에서 ROS 출력 시험을 재실행해 ROS-SIM을 되돌린다.
2. 서명된 native ARM64 artifact 발행 후 Pi readback(ARTIFACT → DEVICE).

## 현재 유효한 금지사항

- API·Nav2·흡수 Control 어디서도 `cmd_vel`을 CORE 밖에서 발행하지 않는다.
- Fleet은 `cmd_vel` 소스가 아니다.
- Pinky+OMX 합성 Asset은 v1이 아니다(D-55, D-71).

## 2026-09-21 supervised traffic-policy status

- CORE는 road evidence를 ROS-free policy로 평가하고 차선 주행 후보를 Command Manager 직전의 원자적 traffic gate에서 제한한다.
- stale/conflict/scene mismatch는 `HOLD`와 zero command다. 정책은 `DISABLED`, `MONITOR_ONLY`, `ENFORCED`로 분리되며 기본값은 `DISABLED`다.
- 관제 stage/apply는 fresh zero velocity 또는 E-stop, `IDLE`/`EMERGENCY`, line-follow OFF를 요구한다. simulation signal은 simulation runtime과 capability가 모두 있어야 한다.
- LOCAL `1005 passed, 11 skipped`; 실제 Chromium stage→apply `1 passed`. 실제 ROS bridge graph와 물리 주행은 여전히 ROS-SIM/DEVICE/FIELD HOLD다.
