---
module: control
logical_modules: [M05, M06, M07, M11]
owner: CONTROL
last_verified: { commit: "b98642f", date: 2026-09-20 }
gates:
  SOURCE:
    state: GO
    evidence: "흡수 패키지 배치·메타데이터·안내 문서 계약 시험 통과 (2026-09-16 재확인, 6 passed) — 폴더 구성, package.xml/README/guide의 CORE 소유권 문구를 단언한다"
    cmd: "python3 -m pytest test/test_control_absorption_package.py -q"
  LOCAL:
    state: GO
    evidence: "998 passed, 26 skipped (2026-09-17 Windows, PYTHONPATH는 ';' 구분, 미커밋 WIP 포함 작업 트리). D-72 S2 뒤 재실행 — 신규 test_map_raster_color_contract.py 3건 포함"
    cmd: "PYTHONPATH=src/control:src python3 -m pytest src/control/test -q"
  ROS-SIM:
    state: HOLD
    blocker: "ROS 2 Jazzy 노드 그래프(sensing/camera/planning/safety-policy) 재실행 증거 없음. 레거시 전체 스택(launch/robot.launch.py)은 CORE와 병행 기동하지 않는다(AGENTS.md, D-38). 2026-09-20 Gazebo Harmonic end-to-end 시도 기록: 번들 무결성·월드 로드 PASS, 물리 충돌·센서 브리지 FAIL — docs/validation/map-260905-update-v2-2026-09-20/result.md. 재실행 전 물리 메시 충돌과 브리지 무출력을 먼저 해소해야 한다"
  ARTIFACT:
    state: HOLD
    blocker: "서명된 ARM64 manifest·immutable digest 발행 전. 흡수된 코드는 deploy가 소유하는 OS 이미지에 번들된다"
  DEVICE:
    state: HOLD
    blocker: "Pi bench Device 설치와 device-readback.sh --json 증거 없음. Control sensor adapter 활성화는 Device 보정 generation에 묶인다(D-47)"
  FIELD:
    state: PARKED
adrs: [D-37, D-38, D-40, D-42, D-47, D-50, D-57, D-58, D-77, D-118, D-119]
plans:
  - docs/plans/2026-09-06-module-split-criteria.md
  - docs/plans/2026-09-12-rosy-control-absorption-plan.md
  - docs/plans/2026-09-12-control-absorption-results.md
  - docs/plans/2026-09-13-control-safety-boundary.md
  - docs/plans/2026-09-13-rosy-os-device-validation-implementation-plan.md
  - docs/plans/2026-09-15-module-harness-design.md
  - docs/plans/2026-09-17-interface-design-implementation-design.md
---
## 지금 상태

- 흡수된 ROS 2 Jazzy 패키지로 sensing/camera·OpenCV/calibration/planning/safety-policy/navigation-session 순수 로직을 제공한다(AGENTS.md).
- 최종 `cmd_vel` 발행과 이동 명령 중재는 CORE 소유다(D-38). 이 패키지의 레거시 전체 스택은 CORE와 병행 기동하지 않는다.
- 흡수된 Control sensor adapter는 기본 비활성이며, 켜면 Device 보정 generation에 묶인다(D-47; `core/progress.md` 참조).
- `web_node`+`dashboard.html`은 레거시 런치 진단 화면이다. 운용자 콘솔이 아니며 compose에 없다(D-77).
- LOCAL 증거는 `8fdd8d2` 기준이다. Windows에서는 `PYTHONPATH`를 `;`로 구분한다.

## 다음 gate

1. ROS Jazzy container에서 control 노드 그래프 시험을 재실행해 ROS-SIM을 되돌린다.
2. 서명된 ARM64 artifact 발행 후 Pi readback으로 Control sensor adapter 활성화 경로를 확인한다(ARTIFACT → DEVICE).

## 현재 유효한 금지사항

- 순수 로직 결정은 `control/control/`, `control/planning/`, `control/sensing/`, `control/watch.py`에만 두고 ROS import를 넣지 않는다(AGENTS.md).
- 이 패키지의 레거시 최종 `/cmd_vel` publisher를 CORE와 나란히 기동하지 않는다(AGENTS.md, D-38).
- `config/robot.yaml`이 단일 공유 파라미터 소스이며 per-node yaml은 이후에만 override한다(AGENTS.md).

## 2026-09-20 adaptive speed authorization status

- Geometry/sensor estimates now have candidate and active certificate states, context binding, evidence digests, bounds, observability checks, and independent holdout promotion.
- Motion envelopes are direction-specific and bind stopping, latency, lateral error, environment, payload, battery, temperature, wheel revision, and the active geometry digest.
- Runtime limiting is fail-closed for stale/unknown evidence and continuously reduces speed using uncertainty plus latency/braking distance. Drift immediately returns authority to at most `0.014 m/s`.
- The Control-to-CORE snapshot carries a numeric `linear_limit`; CORE remains the sole final `cmd_vel` owner.
- Current default and sensor-node publication remain `0.014 m/s`. A higher ceiling requires explicit commissioned configuration and is not active in this change.
- Verified: focused Control `37 passed`; CORE package `895 passed, 11 skipped`; IMU host `4 passed, 10 skipped`.
- Final host Control gate: `1038 passed, 26 skipped`; the startup-profile fixture now supplies the declared empty `web_port` and `web_backend_port` defaults.
- ROS-SIM HOLD: no Jazzy runtime proof for the new policy.
- DEVICE HOLD: no Pi/ARM64 build, BNO055 live readback, stopping trials, `map_260905_update_v2` traversal, or physical clearance proof.
- FIELD HOLD: no unattended complete-route or supervision acceptance.

## 2026-09-20 flexible clearance recovery status

- The fixed 0.08 m execution cap and compatibility fallback are removed from the measured escape executor.
- A fresh proposal must bind `robot_diameter_m` and `max_reposition_m`; the latter cannot exceed the calibrated circumscribed diameter or the current measured corridor.
- Reverse is preferred among equivalent recovery candidates, but forward remains available when rear evidence is unsafe or produces no improvement.
- The episode stops on restored turn clearance, stale scan/proposal, geometry revision change, pose deviation, no progress, hazard, or budget exhaustion. Its bound may shrink but cannot expand while moving.
- Verified in pure logic and the real legacy adapter: `30 passed` focused tests, `102 passed` in the wider recovery/adaptive-speed/certificate/calibration set, and final full Control `1038 passed, 26 skipped`. The active CORE/Nav2 recovery connection remains HOLD to preserve CORE as the only final `cmd_vel` owner.

## 2026-09-20 optional camera ground homography status

- A camera-ground profile is now separated into candidate, eligible, requested, and active states. Reported residuals are ignored; reference and independent validation errors are recomputed from the point pairs.
- The runtime image size, processed rotation, camera profile revision, intrinsic/undistorted-point contract, coordinate semantics, bounded thresholds, independent image names/count/distance span, and four physical attestations all fail closed.
- `camera_ground_mode` keeps `pinhole` as the default. A validated homography can be enabled for the current session from the diagnostic dashboard; the switch cannot override failed checks and is not persisted.
- Board-relative lateral coordinates provide forward distance only. Camera metric output remains advisory and does not create speed or final command authority.
- SOURCE verification is covered by host pure-logic and wiring tests. DEVICE/FIELD remain HOLD until a complete profile, independent captures, measured Pinky Pro distances, and live readback are available.
