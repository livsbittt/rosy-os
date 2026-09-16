# Rosy OS ARM64 ARTIFACT native-Pi 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** D-66 CORE 이미지(`rosy_control`/OpenCV 없음)를 **네이티브 linux/arm64**로 빌드하고 digest까지 기록해 ARTIFACT를 HOLD에서 한 단계 올린다. 호스트 QEMU는 1순위가 아니다.

**Architecture:** `rosy_core`만 `core` 스테이지에 들어간다. Control 센서 워커와 OpenCV는 `io`/Control slice. Hub `ros:jazzy-ros-base` linux/arm64 (2026-09-16)는 CPython/colcon/gcc/cmake 모듈이 0바이트라 QEMU 경로가 막혔다. Dockerfile의 `restore-hollow-python.sh` / `restore-hollow-toolchain.sh`는 건강한 이미지에서는 no-op로 남긴다.

**Tech Stack:** ROS 2 Jazzy, Docker Buildx, Raspberry Pi OS Lite 64-bit, pytest (host, ROS-free).

---

## 0. 고정된 사실 (이 계획의 입력)

- 실행 SoT: `docs/plans/2026-09-13-rosy-os-device-validation-implementation-plan.md`
- 증거 노트: `docs/deployment/arm64-build-notes.md` 섹션 `2026-09-17 D-66 QEMU HOLD`
- HEAD (계획 작성 시점): `c83f44d` on `chore/public-release-prep` = local `main`
- `ac81f2f` core/io digest는 D-66 이전이다. 재사용 금지.
- ARTIFACT / DEVICE / FIELD는 모두 HOLD. 호스트 pytest는 Device GO가 아니다.
- `src/rosy_imu_bno055/**` WIP는 건드리지 않는다.
- 제약: apt/`rosyctl` 없음, Fleet 서버 없음, Pinky+OMX 합성 없음, CORE만 최종 `cmd_vel` (D-2/D-38).

---

## Task 1 — 빌드 경로 고르기

**Files:**
- Read: `docs/deployment/arm64-build-notes.md`
- Read: `deploy/robot/Dockerfile`

**Step 1:** Pi 5에서 `uname -m`이 `aarch64`이고 Docker가 native `linux/arm64`인지 확인한다.

```bash
uname -m
docker version --format '{{.Server.Arch}}'
docker buildx inspect --bootstrap
```

Expected: `aarch64` / `arm64`. QEMU가 보이면 이 계획은 Task 1b로 간다.

**Step 2 (권장):** native Pi에서 `--platform linux/arm64` 없이 `core` 타깃을 빌드한다. Hub 이미지가 여전히 0바이트면 restore 스크립트가 같은 우분투 `.deb`로 채운다.

**Step 1b (호스트 QEMU를 꼭 써야 할 때만):** 2026-09-16 이전 `ros:jazzy-ros-base` linux/arm64 digest를 핀한다. `ac81f2f` 이미지 레이어에서 쓰인 digest를 쓰거나, osrf가 재발행한 건강한 태그를 확인한다. 현재 Hub 태그 `jazzy-ros-base` arm64를 그대로 다시 QEMU하지 않는다.

**Step 3:** 선택한 경로를 `docs/deployment/arm64-build-notes.md`에 한 단락으로 적고 커밋한다.

---

## Task 2 — D-66 `core` 이미지 빌드와 검사

**Files:**
- Modify: `docs/deployment/arm64-build-notes.md` (digest만)
- Test: `src/rosy_core/test/test_robot_runtime.py` (host, 이미 D-66 eviction)

**Step 1:** repo root에서:

```bash
docker buildx build --target core --tag rosy-core:arm64-validation-<HEAD> \
  --file deploy/robot/Dockerfile --progress=plain --load .
```

Native Pi면 `--platform` 생략. QEMU면 `--platform linux/arm64`와 핀된 `ROS_IMAGE`.

**Step 2:** inspect.

```bash
docker inspect --format 'os={{.Os}} arch={{.Architecture}} id={{.Id}}' \
  rosy-core:arm64-validation-<HEAD>
```

Expected: `os=linux arch=arm64`.

**Step 3:** 지원되는 entrypoint로 검사한다. `--entrypoint python3` 금지.

```bash
docker run --rm rosy-core:arm64-validation-<HEAD> bash -lc '
python3 - <<PY
import importlib.util, platform
print("machine", platform.machine())
for n in ("rclpy", "rosy_core", "cv2", "rosy_control"):
    print(n, "present" if importlib.util.find_spec(n) else "absent")
PY
test ! -d /opt/rosy_ws/install/rosy_control
'
```

Expected: `machine aarch64`, `rclpy`/`rosy_core` present, `cv2`/`rosy_control` absent.

**Step 4:** image ID를 `arm64-build-notes.md`에 기록. ARTIFACT는 아직 HOLD (서명/registry/Pi readback 없음).

**Step 5:** 노트만 커밋. WIP `Dockerfile`/IMU는 stage하지 않는다.

---

## Task 3 — `io` 이미지

같은 Dockerfile `--target io`, 태그 `rosy-io:arm64-validation-<HEAD>`.

검사: `arch=arm64`, entrypoint로 `sllidar_ros2`/`rosy_bringup` 존재. `io`는 OpenCV를 가져도 된다. CORE와 같이 최종 `cmd_vel`을 발행하면 안 된다.

노트의 io ID를 갱신하고 커밋.

---

## Task 4 — Device Task 8으로 넘기기

Pi 설치·identity·systemd·readback은 기존 계획 Task 8. 이 계획의 산출물은 **새 digest가 적힌 노트**이지 DEVICE GO가 아니다.

서명/registry는 기존 계획 Task 7 잔여. digest 없이 서명하지 않는다.

---

## 명시적 비범위

- 호스트 QEMU로 현재 Hub `jazzy-ros-base` arm64를 다시 장시간 빌드
- `ac81f2f` digest 재사용
- Fleet 서버, Pinky+OMX 합성, `src/rosy_imu_bno055/**` WIP
- ARTIFACT GO 선언 (서명·Pi readback 전)
