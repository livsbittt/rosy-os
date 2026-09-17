---
module: rosy_gz_sim
logical_modules: [M03, M07]
owner: SIM
last_verified: { commit: "uncommitted", date: 2026-09-15 }
gates:
  SOURCE:
    state: HOLD
    blocker: "유일한 시험 src/rosy_gz_sim/test/test_gz_multi_core.py가 pytest.importorskip('launch')로 이 Windows 호스트에서 전부 skip된다(2026-09-15, 1 skipped) — ROS 2 launch 패키지 없이는 재실행 불가"
  LOCAL:
    state: HOLD
    blocker: "동일 — 유일한 시험이 skip만 하므로 증거가 아니다(1 skipped, 2026-09-15). ROS 2 Jazzy + launch/launch_ros 설치 후 재실행 필요"
  ROS-SIM:
    state: HOLD
    blocker: "Gazebo/ros_gz multi-robot 시나리오(gz_multi.launch.py) 미실행. ROS 2 Jazzy + Gazebo 환경에서 재실행 필요"
  ARTIFACT:
    state: N/A
  DEVICE:
    state: N/A
  FIELD:
    state: N/A
adrs: [D-4, D-33, D-49]
plans:
  - docs/plans/2026-09-08-swarm-formation-slice-design.md
  - docs/plans/2026-09-08-swarm-formation-slice.md
  - docs/plans/2026-09-08-swarm-formation-slice-results.md
  - docs/plans/2026-09-15-module-harness-design.md
---
## 지금 상태

- Gazebo worlds/models/ros_gz bridge params/lamp plugin과 N대 네임스페이스 로봇을 띄우는 `gz_multi.launch.py`를 제공한다(`robots`, `mode:=nav|slam`, `core:=true`로 로봇별 `rosy_core` 인스턴스까지 spawn).
- `CMakeLists.txt`가 aarch64에서 `return()`한다 — Pi 이미지는 Gazebo를 포함하지 않는다. 이 패키지는 로봇 릴리스 이미지의 일부가 아니다.
- 유일한 host pytest(`test_gz_multi_core.py`)는 `launch`/`launch_ros`가 있어야 실행되며, 이 Windows 세션에는 ROS 2가 없어 `pytest.importorskip("launch")`로 전체 skip된다. 설계 문서의 규칙대로 skip은 증거가 아니다.
- `swarm-formation-slice-results.md` Task 12 Step 5(`gz_multi robots:=2 mode:=nav core:=true` 런타임 확인)와 Task 14 시나리오는 미실행으로 남아 있다.
- 작업 트리에 이 모듈 자체의 미커밋 코드 변경은 없다(`AGENTS.md`류만 신규/수정).

## 다음 gate

1. ROS 2 Jazzy + `launch`/`launch_ros`가 설치된 환경(컨테이너 등)에서 `test_gz_multi_core.py`를 실제로 실행해 SOURCE/LOCAL을 재판정한다.
2. 같은 환경에서 `gz_multi.launch.py` 멀티로봇 시나리오를 실행해 ROS-SIM 증거를 만든다(Task 12 Step 5, Task 14).
3. ARTIFACT/DEVICE/FIELD는 이 패키지가 로봇 이미지에 포함되지 않는 한 계속 N/A다 — 승격 대상이 아니다.

## 현재 유효한 금지사항

- `CMakeLists.txt`의 aarch64 `return()`을 "고치지" 않는다. Pi 이미지는 Gazebo를 싣지 않는다.
- mapper `scan_topic`이 자동으로 네임스페이스 처리된다고 가정하지 않는다 — 로봇별로 override가 필요할 수 있다.
- 이 패키지에서 로봇 이미지 편입(ARTIFACT/DEVICE 승격)을 시도하지 않는다. 시뮬레이션 전용 설계다.
