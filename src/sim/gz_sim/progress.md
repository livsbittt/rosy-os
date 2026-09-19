---
module: gz_sim
logical_modules: [M03, M07]
owner: SIM
last_verified: { commit: "dc89264", date: 2026-09-17 }
gates:
  SOURCE:
    state: GO
    evidence: "test_gz_package_contract 2 passed, test_world_to_map 6 passed (2026-09-17 Windows). launch 시험은 skip이며 SOURCE가 아니다"
    cmd: "python -m pytest src/gz_sim/test/test_gz_package_contract.py src/gz_sim/test/test_world_to_map.py -q"
  LOCAL:
    state: GO
    evidence: "D-114 ros_gz_bridge lock, D-115 spawn_xy/initialpose seed (2026-09-18 Windows). Gazebo 런타임은 ROS-SIM"
    cmd: "python -m pytest src/gz_sim/test/test_gz_package_contract.py src/gz_sim/test/test_world_to_map.py -q"
  ROS-SIM:
    state: HOLD
    blocker: "gz_multi.launch.py 멀티로봇 시나리오 미실행. ROS 2 Jazzy + Gazebo 필요 (Task 14)"
  ARTIFACT:
    state: N/A
  DEVICE:
    state: N/A
  FIELD:
    state: N/A
adrs: [D-4, D-33, D-49, D-79, D-114, D-115, D-117, D-118, D-120]
plans:
  - docs/plans/2026-09-08-swarm-formation-slice-design.md
  - docs/plans/2026-09-08-swarm-formation-slice.md
  - docs/plans/2026-09-08-swarm-formation-slice-results.md
  - docs/plans/2026-09-15-module-harness-design.md
---
## 지금 상태

- `gz_multi.launch.py`로 N대 네임스페이스 로봇을 띄운다. 도메인 하나 + ros_gz_bridge (D-114). `domain_bridge` 없음.
- `mode:=nav` 는 spawn 좌표를 `{ns}/initialpose` 로 심는다 (D-115). odom (0,0) 을 관제 pose 로 쓰지 않는다.
- `world_to_map.py`가 박스 충돌체에서 정답 점유 격자를 만든다. Gazebo 없이 Windows에서 돈다.
- aarch64 CMake는 `return()` — Pi 이미지에 Gazebo를 싣지 않는다.
- ROS-SIM(Task 14 실측)은 HOLD. SOURCE/LOCAL은 host-contract + world_to_map이다.

## 다음 gate

1. ROS 2 Jazzy + Gazebo에서 `gz_multi robots:=2 mode:=nav core:=true`를 실행해 ROS-SIM을 되돌린다.
2. ARTIFACT/DEVICE는 이 패키지가 로봇 이미지에 없으므로 N/A.

## 현재 유효한 금지사항

- aarch64 `return()`을 고치지 않는다.
- 이 패키지를 로봇 이미지에 넣지 않는다.
