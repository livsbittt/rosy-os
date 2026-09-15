<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-15 -->

# plans

## Purpose

Dated design and execute plans (2026-08-31 onward). These are the working trail for Pi runtime, motors, power, dashboard, docking, battery integrity, Wi-Fi, ROS graph observability, and OS image/release.

## Key Files

| File | Description |
|------|-------------|
| `2026-08-31-raspberry-pi-runtime.md` | Pi runtime split (core/motor/io) |
| `2026-09-01-raspberry-pi-wifi-deployment.md` (+ `-design`) | Headless Wi-Fi/SSH image |
| `2026-09-01-motor-control-contracts.md` (+ `-design`) | ROS-free MotorController contracts |
| `2026-09-01-pi-motor-commissioning.md` (+ `-design`) | UART / Dynamixel bench |
| `2026-09-01-deep-power-states-design.md` | IDLE/STANDBY duty cycling (D-24/D-25) |
| `2026-09-01-proximity-wake-standby.md` (+ `-design`) | Ultrasonic wake |
| `2026-09-01-rosy-dashboard.md` (+ `-design`) | Embedded FastAPI dashboard (D-23) |
| `2026-09-01-ros-network-observability.md` (+ `-design`) | ROS graph / DDS telemetry |
| `2026-09-01-rosy-os-v1-image-release-design.md` | Signed image + Host Agent |
| `2026-09-02-battery-integrity-low-battery-alert.md` (+ `-design`) | SAF-005 curve, hysteresis, D-27 shutdown sentinel |
| `2026-09-02-docking-station.md` (+ `-design`) | Dock SM; last cm is sensor-closed-loop |
| `2026-09-03-runtime-maintainability-rules.md` | Runtime slice module rules (catalog, launch compose, Nav2 policy) |
| `2026-09-05-vision-accelerator-shield-design.md` | Pi 5 HAT/M.2 AI Kit vision offload (D-29 proposed; compose profile `vision`) |
| `2026-09-08-swarm-formation-slice-design.md` | Fleet-less N-robot formation slice: `rosy_fleet` seed (geometry, slot assignment, relay, FOR-004 session), `gz_multi core:=true`, sim bench; D-35 candidate |
| `2026-09-08-swarm-formation-slice.md` (+ `-results`) | Execution plan for that slice (15 TDD tasks, ROS-free until the sim bench) and the results file that records what the sim bench measured and what it could not |
| `2026-09-13-rosy-os-device-validation-implementation-plan.md` | Rosy OS 기능 구현·자동화 시험·ARM64 artifact·Pi Device 설치/readback·Pinky Pro/OMX 현장 승격 gate |
| `2026-09-14-site-middleware-role-fabric-design.md` | 관제 PC Fleet 서버가 모으고 흩뜨림. 디바이스는 계약 버스만. 역할 단일 (D-59) |
| `2026-09-14-site-middleware-role-fabric.md` | D-59 실행: 역할 가드 + ROS-free SiteHub gather/scatter (UI·영상·outbound·Pi 제외) |
| `2026-09-15-navigation-swarm-split-design.md` | 추종을 navigation에서 분리해 `rosy_core.swarm`으로 (D-60) |
| `2026-09-15-navigation-swarm-split.md` | D-60 실행: poses/manager 이동, navigation import 금지, 동작 불변 |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- Read the matching `-design.md` before changing power, docking, battery, or release code.
- Do not treat these as the API contract; that remains `docs/reference/`.
- Branch `feat/swarm-formation-slice` maps to `2026-09-08-swarm-formation-slice-design.md`.

### Testing Requirements

Each execute plan names pytest modules (usually `src/rosy_core/test/test_power.py`, `test_battery.py`, `test_docking.py`, or repo `test/`).

### Common Patterns

Filename `YYYY-MM-DD-kebab.md`; design and execute are separate files.

## Dependencies

### Internal

- Code under `src/rosy_core`, `src/rosy_bringup`, `deploy/`

### External

None.

<!-- MANUAL: -->
