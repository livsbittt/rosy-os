---
module: rosy_description
logical_modules: [M06, M07]
owner: 로봇 통합
last_verified: { commit: "dc89264", date: 2026-09-17 }
gates:
  SOURCE:
    state: GO
    evidence: "test_urdf_surface 1 passed — package name과 wheel_joint 매크로 (2026-09-17 Windows)"
    cmd: "python -m pytest src/rosy_description/test/test_urdf_surface.py -q"
  LOCAL:
    state: GO
    evidence: "동일. xacro 렌더는 ROS-SIM"
    cmd: "python -m pytest src/rosy_description/test/test_urdf_surface.py -q"
  ROS-SIM:
    state: HOLD
    blocker: "robot_state_publisher·Gazebo(rosy_gz.urdf.xacro)의 xacro 렌더와 TF 트리 확인 미실행. ROS 2 Jazzy 환경 필요"
  ARTIFACT:
    state: HOLD
    blocker: "io 이미지에 포함된다(deploy/robot/Dockerfile `COPY src/rosy_description`, `--packages-select`에 포함; meshes는 `RUN mkdir -p`로 빈 폴더만 생성). 서명 manifest·OCI archive·immutable registry digest 발행 전"
  DEVICE:
    state: HOLD
    blocker: "Pi OS Lite bench Device의 install-pi.sh 설치, verify-pi.sh, device-readback.sh --json 증거 없음"
  FIELD:
    state: PARKED
adrs: [D-4]
plans:
  - docs/plans/2026-09-12-rosy-os-module-evaluation-maintenance-design.md
  - docs/plans/2026-09-13-rosy-os-device-validation-implementation-plan.md
  - docs/plans/2026-09-15-module-harness-design.md
---
## 지금 상태

- 로봇 URDF/xacro, visual/collision meshes, RViz 모델 뷰. 첫 하드웨어는 Pinky Pro다. `namespace`/`frame_prefix`를 지원한다(D-4).
- 모듈 경로는 clean이지만 SOURCE 증거 시험이 미커밋 WIP가 있는 `deploy/robot/Dockerfile`을 읽으므로 `last_verified`는 `uncommitted`다.
- `deploy/robot/Dockerfile`의 io-build 단계가 `rosy_description`을 복사·빌드한다. 단 `.dockerignore`가 `src/rosy_description/meshes/**`를 build context에서 제외하고, Dockerfile이 `RUN mkdir -p src/rosy_description/meshes`로 빈 폴더만 만든다 — meshes 자체는 device 이미지에 실리지 않는다.
- Gazebo는 `rosy_gz.urdf.xacro`를 쓴다. `left_wheel_joint`/`right_wheel_joint` 이름은 `rosy_bringup`과 맞춰야 한다.

## 다음 gate

1. `left_wheel_joint`/`right_wheel_joint` 이름과 xacro 파싱을 고정하는 host 계약 시험을 추가해 SOURCE를 채운다.
2. ROS 환경에서 `view_robot.launch.py` 로컬 구동과 ament_lint(CMake)를 실행해 LOCAL을 채운다.
3. 서명된 native ARM64 artifact 발행 후 Pi readback(ARTIFACT → DEVICE), deploy/rosy_core와 동일 체인.

## 현재 유효한 금지사항

- Gazebo 전용 플러그인/토픽을 `rosy_gz.urdf.xacro`에서 깨지 않는다.
- inertia helper는 `urdf/common/insert_inertia.urdf.xacro`에 유지한다.
- `left_wheel_joint`/`right_wheel_joint` 이름을 `rosy_bringup`과 어긋나게 바꾸지 않는다.
