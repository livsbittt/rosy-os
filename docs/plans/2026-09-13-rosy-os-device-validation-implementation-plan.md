# Rosy OS 기능·Device 검증 통합 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 흡수된 `rosy_control` 기능을 Rosy OS의 단일 명령·안전 경로에 연결하고, 자동화 시험에서 ARM64 이미지·Device 설치·readback·Pinky Pro 현장 인수까지 재현 가능한 증거 사슬을 만든다.

**Architecture:** `rosy_core`는 FastAPI/rclpy와 최종 `cmd_vel` 발행자로 남긴다. `rosy_control`은 ROS 의존성이 낮은 worker와 sensor-only typed evidence를 제공한다. Device는 Raspberry Pi OS Lite 64-bit 호스트에서 서명된 ROS 2 Jazzy ARM64 컨테이너를 실행하며, `core`를 먼저 고정 운용하고 이후 `motor`와 `hardware` 프로필을 순서대로 승격한다.

**Tech Stack:** ROS 2 Jazzy, Python 3.12, rclpy, FastAPI, pytest, NumPy/OpenCV, colcon, Docker Buildx, Raspberry Pi OS Lite 64-bit, systemd, Docker Compose, signed release tooling.

---

## 1. 기준선과 범위

현재 흡수 작업은 소스·문서·정적 테스트 기준으로 완료되었지만, `rosy_core` 실행 그래프에서 `rosy_control` sensor-only adapter를 실제로 켜는 작업, ARM64 이미지에 패키지를 넣는 작업, Pi 설치와 물리 장치 검증은 남아 있다. 기존 `src/rosy_control/launch/robot.launch.py`는 legacy full stack이므로 CORE와 함께 실행하지 않는다. 최종 `cmd_vel` publisher는 `rosy_core/bridge/ros_bridge.py` 한 곳이어야 한다.

증거는 서로 대체하지 않는 다음 계층으로 기록한다.

| 계층 | 확인 내용 | 현재 상태 | 승격 조건 |
| --- | --- | --- | --- |
| SOURCE | 소스·ADR·경계·패키지 구조 | GO | 변경마다 diff와 ADR 연결 |
| LOCAL | Windows의 순수 Python/문서/계약 테스트 | GO(환경 의존 일부 제외) | 반복 가능한 명령과 결과 저장 |
| ROS-SIM | ROS 2 Jazzy graph, parameter, topic, safety 시나리오 | GO(기존 증거) | container에서 재실행 가능한 smoke |
| ARTIFACT | linux/arm64 이미지·digest·서명·manifest | HOLD | 빌드와 서명 readback |
| DEVICE | Pi OS 설치·identity·systemd·컨테이너·센서 readback | HOLD | 설치 전후 manifest와 health 증거 |
| FIELD | Pinky Pro 구동·정지·카메라·적재·암 | PARKED | 안전 담당자와 실물 시험 승인 |

각 단계의 결과는 `GO`, `HOLD`, `PARKED` 중 하나로 남기며, 상위 계층 결과를 하위 계층의 증거로 표현하지 않는다.

## 2. 작업 순서

### Task 0 — 기준선 고정과 시험 환경 확인

1. `docs/plans/2026-09-12-rosy-os-control-integrated-design.md`, `docs/plans/2026-09-12-control-absorption-results.md`, `docs/reference/ROSY ADR Log.md`, `docs/deployment/arm64-build-notes.md`, `deploy/robot/install-pi.sh`, `deploy/robot/verify-pi.sh`를 읽고 계획의 입력 revision을 기록한다.
2. `git status --short`, `git rev-parse HEAD`, `git worktree list`를 저장한다. `src/rosy_imu_bno055/**`의 기존 WIP는 명시적 파일 목록 없이 stage/reset/overwrite하지 않는다.
3. 순수 테스트를 실행한다.

   ```powershell
   python -m pytest test/test_control_absorption_package.py test/test_network_topology_contracts.py -q --basetemp .pytest-tmp-device
   ```

4. ROS Jazzy 컨테이너에서 `/opt/ros/jazzy/lib/python3.12/site-packages`를 보존한 상태로 `rosy_core`와 `rosy_control`의 graph/parameter smoke를 실행한다. Windows에서 `bash` 또는 `openssl`이 없는 경우 해당 실패를 환경 제한으로 기록하고 성공으로 포장하지 않는다.

**산출물:** 기준선 revision, 명령, 통과/실패/skip 수, 환경 제한을 `docs/plans/2026-09-12-control-absorption-results.md`에 연결한다.

### Task 1 — ROS-free 정책 계약을 먼저 잠근다

대상은 `src/rosy_control/rosy_control/control/command_gate.py`, `lidar_guard.py`, `obstacle_risk.py`, `policy_handoff.py`와 해당 단위 테스트다.

- `GateInputs`, `Observations`, `ControlPolicyProducer`의 required sensor, timestamp, sequence, revision, evidence를 불변 snapshot으로 유지한다.
- non-finite 수치, 누락·stale 센서, revision 불일치, 순서 역전은 fail-closed 한다.
- producer는 ROS publisher나 e-stop endpoint를 만들지 않고 후보 정책과 근거만 반환한다.
- candidate와 최종 `cmd_vel`을 혼동하지 않도록 이름과 테스트 fixture를 분리한다.

시험은 정상 후보, missing/stale/non-finite, revision 변경, immutable evidence, sequence 역전, stop/zero candidate, 멱등 재평가를 포함한다.

```powershell
python -m pytest src/rosy_control/test -q --basetemp .pytest-tmp-control
```

### Task 2 — CORE에 명시적 sensor-only adapter를 연결한다

새 파일 `src/rosy_core/rosy_core/bridge/control_sensor_adapter.py`를 만들고 `rosy_core/node.py`, `rosy_core/services.py`, `rosy_core/safety/manager.py`와 연결한다.

- adapter는 camera/LiDAR/odom/IMU의 ROS 입력을 typed observation으로 변환하여 `ControlPolicyProducer`에 전달한다.
- 기본 프로필은 `disabled`다. 비활성일 때 callback, timer, device access, command side effect가 없어야 한다.
- 활성화할 때도 같은 rclpy executor 안에서 worker를 구동하며 최종 `cmd_vel`, e-stop HTTP route, legacy calibration authority를 만들지 않는다.
- `SafetyManager.bind_control_policy`가 실제 production node에서 호출되는지 확인하고, missing handoff는 자동으로 정지 후보가 되게 한다.
- CORE가 기존 `RosBridge`의 단일 최종 publisher를 유지하는지 graph guard로 검증한다.

시험 항목은 adapter disabled/enabled, camera/LiDAR/odom 누락, invalid transform, stale timestamp, callback 예외, node restart, revision 변경, executor shutdown, duplicate publisher 검출이다.

### Task 3 — 최종 출력과 안전 상태를 검증한다

`src/rosy_core/rosy_core/bridge/ros_bridge.py`, `src/rosy_core/rosy_core/safety/manager.py`, `src/rosy_control/rosy_control/safety/node.py`의 handoff를 정리한다.

- 정책 후보는 timestamp·sequence·revision을 포함하고, 최종 발행 직전에 다시 stale/범위/e-stop 조건을 확인한다.
- e-stop 해제는 fresh evidence와 명시적 operator action을 모두 요구한다.
- legacy launch와 CORE를 동시에 올리는 경우를 시작 단계에서 거부한다.
- 취소·정지는 늦게 도착한 callback이 덮어쓸 수 없도록 generation과 sequence를 비교한다.

`python -m pytest src/rosy_core/test -q`와 ROS graph smoke에서 publisher 수, stale hold, e-stop release, late-cancel, clean shutdown을 확인한다.

### Task 4 — calibration 적용·readback과 bounded sweep을 추가한다

calibration snapshot/storage, `rosy_control/safety/node.py`, CORE profile/manager를 변경 대상으로 삼는다.

- schema, sensor ID, generation, digest, 범위와 단위를 검증한다.
- 적용 전에는 모터를 정지시키고, 임시 파일과 atomic rename으로 generation을 바꾼다.
- write 후 readback이 입력 digest와 다르면 새 generation을 폐기하고 이전 정상 generation을 유지한다.
- 센서·안전 증거가 부족하면 bounded sweep을 시작하지 않는다. sweep은 simulation에서 먼저 재현하고, Device에서는 명시적 opt-in으로만 연다.

시험은 identity mismatch, schema mismatch, 범위 초과, digest 불일치, rollback, 재시작 후 readback, sweep timeout과 stop-distance를 포함한다.

### Task 5 — OpenCV 전처리 worker를 선택형 기능으로 제품화한다

현재 `src/rosy_control/rosy_control/vision/camera_detect_node.py`의 HSV 결과는 바닥·절벽·전경 evidence이며 semantic box/grasp 판정이 아니다. 다음을 분리한다.

- camera worker의 입력 해상도·FPS·회전·노출을 profile로 고정하고, frame ID/time/revision/drop/latency/CPU/memory를 telemetry로 남긴다.
- `requirements*.txt`, `deploy/robot/Dockerfile`, `deploy/robot/compose.yaml`에 선택형 vision 의존성을 추가하되 CORE 컨테이너에 광범위한 `/dev`를 주지 않는다.
- Picamera2/CSI를 host service로 둘지 least-privilege container로 둘지는 실제 Pi에서 동일 시나리오를 비교한 뒤 결정한다.
- 이미지 전처리 evidence는 LiDAR/IR metric safety authority를 대체하지 않는다.

자동 시험은 고정 frame fixture, corrupt/empty frame, 색상·조명 변화, frame drop, latency budget, worker restart를 포함한다. 실제 카메라 시험은 Device 계층으로 남긴다.

### Task 6 — Nav2/ControlBackend와 OMX 경계를 고정한다

Nav2와 absorbed Control backend를 동일한 scenario fixture로 비교하고 한 번에 하나의 backend만 활성화한다. cancel, timeout, stale route, obstacle detour, stop distance 결과를 동일한 evidence schema로 기록한다.

OMX는 robot-local action capability로만 둔다. 모델(신형 OMX-F/OMX-AI 또는 구형 RM-X52-TNM), mount, payload, 전원 budget, hand-eye calibration, collision/interlock, recovery가 모두 정해지고 물리 시험을 통과하기 전에는 capability와 Device profile을 disabled로 유지한다. Pinky Pro에 실을 박스의 크기·질량·무게중심은 측정값으로 대체하기 전까지 요구사항 가정으로만 표시한다.

### Task 7 — linux/arm64 artifact를 재현 가능하게 만든다

`deploy/robot/Dockerfile`의 core/io build stage에 필요한 `rosy_control` 패키지와 worker 의존성을 추가하되, 기본 core/motor/hardware profile의 경계를 유지한다. `deploy/robot/compose.yaml`에는 vision/arm capability를 별도 profile로 둔다.

- `inputs.lock.yaml`, package manifest, source revision을 artifact metadata에 넣는다.
- build 후 이미지 안에 accepted worker가 있고 legacy publisher가 없으며 CORE에 device binding이 없음을 검사한다.
- Buildx 실행 예:

  ```powershell
  docker buildx build --platform linux/arm64 --target core -t <registry>/rosy-core:<sha> --file deploy/robot/Dockerfile --load .
  docker image inspect <registry>/rosy-core:<sha>
  ```

- registry digest, manifest, 서명과 검증 결과를 기록한다. 이미지 존재만으로 Device 설치나 현장 운용을 GO로 만들지 않는다.
- x86 Docker Desktop에서 ARM64 binfmt가 없으면 `exec format error`가 발생한다. 이 경우
  native ARM64 Pi/build host 또는 승인된 binfmt builder를 준비하기 전까지 ARTIFACT는 HOLD다.

### Task 8 — Raspberry Pi OS Device 설치와 readback을 구현한다

대상 Device는 Raspberry Pi OS Lite 64-bit 호스트이며, 초기에는 모터·암을 연결하지 않은 bench device다.

1. OS image, hostname, Wi-Fi/SSH, 시간 동기화, UART4, Docker와 최소 host package를 준비한다.
2. `deploy/robot/deploy-from-windows.ps1 -RobotNumber 1 -PiHost <pinky-host> -PiUser rosy`로 immutable `/opt/rosy`를 배포한다. `ROSY_ROBOT_NUMBER`가 없거나 충돌하면 설치를 중단한다.
3. Pi에서 `deploy/robot/verify-pi.sh`와 `deploy/robot/runtime-mode.sh up`을 실행하여 identity, config generation, unit, container health를 확인한다.
4. `rosy-core`를 stationary 상태로 올리고 readback한다: robot ID, profile, capabilities, image digest, source revision, config generation/digest, container ID, ROS graph, 최종 `cmd_vel` publisher 수.
5. `/opt/rosy/deploy/robot/device-readback.sh --json` 결과와 설치 전 manifest를 함께 보관한다. SSH 성공이나 HTTP 200만으로 설치 성공을 선언하지 않으며 credential은 readback에 포함하지 않는다.

### Task 9 — Device commissioning을 위험도 순서로 진행한다

- D0: Pi OS/SSH/time/identity — GO
- D1: signed ARM64 artifact/readback — HOLD until Task 7
- D2: core stationary health/graph — HOLD until Task 8
- D3: sensor-only camera/LiDAR/odom/IMU — HOLD until real hardware attached
- D4: motor runtime down 상태의 wiring/encoder/power probe — `verify-motors.sh`로 수행
- D5: deadman/e-stop/stale evidence/tilt/pickup/cancel/stop-distance controlled motion — safety owner 입회
- D6: pallet/box placement와 반복성 — 측정된 payload와 workspace에서만 수행
- D7: OMX arm interlock, hand-eye, grasp/release — 모델·mount·payload 승인 후 수행
- D8: rollback/reboot/update/maintenance — signed generation과 old generation readback

각 단계가 실패하면 zero hold와 이전 정상 generation을 유지하고 다음 단계로 진행하지 않는다. D7까지 통과하기 전에는 OMX capability를 API와 UI에 노출하지 않는다.

### Task 10 — 운영·롤백·유지보수까지 닫는다

`deploy/robot/systemd`, release/deploy scripts, operator/admin diagnostics, `docs/deployment` runbook과 smoke test를 함께 갱신한다.

- 활성화는 source revision → image digest → manifest/signature → Device readback의 연결을 보장한다.
- start/health/calibration mismatch가 나면 새 generation을 활성화하지 않고 이전 generation으로 유지한다.
- 일반 operator 화면에는 동작·상태만 두고, ID/token/error/grant/artifact/SHA-256 같은 내부 진단은 관리자 diagnostics에 둔다.
- 매 릴리스마다 install, verify, rollback, reboot, log collection, disk cleanup, key rotation 절차를 dry-run한다.

## 3. 실행 명령과 증거 형식

모든 단계는 `command`, `input revision`, `environment`, `result`, `artifact/digest`, `next gate` 필드를 가진 Markdown 또는 JSON evidence를 생성한다. 순수 테스트와 ROS-SIM은 CI에서 매번 실행하고, ARTIFACT/DEVICE/FIELD는 장비·서명 키·현장 로그가 있는 실행에서만 GO로 변경한다.

계획 구현 중 각 task는 작은 변경 단위로 커밋한다. 커밋 전에는 `git diff --check`와 관련 focused test를 실행하며, 현재 IMU WIP는 stage 대상에서 제외한다. ARM64 build나 Pi SSH가 없는 Windows 세션에서는 계획과 fixture/test harness까지만 진행하고 실제 gate는 HOLD로 남긴다.

## 4. Definition of Done

1. `rosy_control` sensor-only 기능이 명시적 profile로 CORE에 연결되고, 최종 `cmd_vel` publisher가 하나다.
2. 정책·adapter·calibration·OpenCV worker·rollback에 focused test와 ROS graph smoke가 있다.
3. ARM64 이미지가 source revision, digest, 서명, profile metadata와 함께 재현된다.
4. Pi OS Device 설치가 `install-pi.sh`/`verify-pi.sh`와 readback 증거로 반복된다.
5. motor·camera·safety·payload·OMX 시험 결과가 각각 독립 계층으로 기록된다.
6. 문서·ADR·runbook이 실제 경로와 일치하며, 미완료 실물 항목은 `HOLD` 또는 `PARKED`로 남는다.

현재 전체 상태는 **IN_PROGRESS**다. SOURCE/일부 LOCAL·ROS-SIM은 GO이고, ARTIFACT/DEVICE/FIELD는 아직 HOLD 또는 PARKED다.

---

## 2026-09-13 implementation checkpoint: calibration and Device handoff

The current software slice now has a concrete startup path for Device-local calibration:

1. The packaged `src/rosy_core/config/rosy_default.yaml` keeps the sensor adapter and calibration loader disabled. A Device overlay may set `control.sensor_adapter.enabled: true` and provide `calibration.required: true`, an exact record path, `data_root`, active generation, and the five-field identity context.
2. `RosyCoreNode` fills missing `active_generation` and `data_root` from `ROSY_DATA_GENERATION` and `ROSY_DATA_PATH`. The adapter loads and validates the snapshot before constructing a ROS worker, so a stale generation, bad digest, selector error, or path escape fails closed without creating the worker.
3. Only the seven measured SafetyNode values are admitted. An explicit override must equal the snapshot value. The worker is still `sensor_only`; `SafetyManager` and the existing CORE bridge retain final command ownership. The loaded snapshot revision and digest are available for administrator diagnostics.
4. Focused tests cover pre-construction load, conflict rejection, generation mismatch, disabled non-access, node environment binding, and packaged default opt-in. This is LOCAL/ROS-SIM evidence only; it does not certify sensors, motors, or arm motion.

Device enablement remains a staged operation. Publish an immutable signed ARM64 image and manifest first; install Raspberry Pi OS Lite 64-bit and `/opt/rosy`; run `verify-pi.sh`; capture `device-readback.sh --json`; then enable calibration only after the stationary graph and sensor gates pass. Keep the previous generation active on any mismatch and record the new readback before moving to motor, box/pallet, or OMX commissioning. OMX model, mount, payload, power, hand-eye, collision interlock, and recovery remain PARKED until measured on the Pinky Pro.

## 2026-09-13 implementation checkpoint: bounded OpenCV worker

The optional camera path now has a reusable ROS-free preprocessing boundary in
`src/rosy_control/rosy_control/sensing/camera_worker.py`:

1. `CameraPreprocessProfile` fixes width, height, FPS, quarter-turn rotation,
   profile revision and the maximum processing latency.
2. `CameraPreprocessWorker` validates BGR8 frames, rejects wrong resolution,
   rotates only after validation, counts frame gaps and out-of-order IDs, and
   marks corrupt or over-budget frames as unavailable evidence.
3. `CameraTelemetry` is JSON-safe and secret-free. It carries frame identity,
   profile revision, dimensions, drop count, processing/capture age, CPU time,
   memory high-water mark and quality reason.
4. `camera_detect_node` keeps its existing HSV evidence and camera policy, but
   routes frames through the worker and publishes `camera/telemetry`. No camera
   output becomes a command or safety authority; semantic box/grasp detection
   is still not implemented.

The worker and existing camera tests pass locally (`991 passed, 26 skipped` for
the full `src/rosy_control/test` suite). This advances SOURCE/LOCAL evidence;
CSI timing, Picamera2 access, and real frame-quality acceptance remain HOLD at
the Device/FIELD gates until a Raspberry Pi is available.
