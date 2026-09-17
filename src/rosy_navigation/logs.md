# rosy_navigation logs

추가만 한다. 형식: [module harness 설계](../../docs/plans/2026-09-15-module-harness-design.md) §4.2.
2026-09-15 이전 이력은 [Device 검증 계획](../../docs/plans/2026-09-13-rosy-os-device-validation-implementation-plan.md)과 `git log -- src/rosy_navigation`를 본다.

## 2026-09-15 · uncommitted · docs(harness): start the rosy_navigation harness record
- 변경: `progress.md`, `logs.md` 추가
- 증거: `python -m pytest test/test_nav2_hardware_slice.py test/test_footprint_profiles.py test/test_nav2_profile_limits.py test/test_nav2_bandwidth_contracts.py test/test_flask_launch_removed.py -q` 36 passed (2026-09-15 Windows, 미커밋 WIP 포함 작업 트리); `python -m pytest test/test_nav2_profile_limits.py -q` 5 passed
- gate 변화: 없음. SOURCE/LOCAL GO, ROS-SIM/ARTIFACT/DEVICE HOLD, FIELD PARKED를 처음 기록
- 결정: D-61 Proposed
- 교훈: 없음

## 2026-09-17 · uncommitted · fix(nav): 좁은 통로에서 실제로 완주하게 만든 네 가지
- 변경: 전역 플래너를 NavFn → `nav2_smac_planner::SmacPlanner2D`, `allow_unknown: false`, 생성 맵 4종의 `free_thresh` 0.25 → 0.196, 새 맵 `rosy_maze`/`rosy_swarm_bench` 추가, `rosy_factory` 맵을 slam_nav 로 재작성(미지 1476 → 1016 셀)
- 증거: WSL ROS 2 Jazzy + Gazebo. `gz_multi robots:=2 mode:=nav world_name:=rosy_maze.world` (인자 없이 월드 프로필만)로 두 대가 4구간 뱀형 미로를 완주 — `rosy_01` ARRIVED (1.98, 2.19), `rosy_02` 는 폭 0.55 m 문을 지나 ARRIVED (2.44, -2.34), 305 s. 공장 단독 8/8 목표 ARRIVED. 호스트 시험 2994 passed, 54 skipped (기존 rosy_control 실패 2건은 무관)
- gate 변화: 없음. ROS-SIM 증거는 쌓였으나 gate 승격은 커밋 뒤 재실행으로 판정한다
- 결정: 없음
- 교훈: 네 가지가 각각 단독으로 전 구간 실패를 만들었고 증상이 모두 "경로를 못 만든다"로 같았다. (1) `free_thresh` 0.25 는 미지 픽셀 205(shade 0.196)를 자유로 읽어 맵 바깥을 뚫어 놓는다. (2) 그 상태에서 `allow_unknown: true` 면 플래너가 벽 너머 지름길을 고른다. (3) NavFn 은 전위장을 만들어 놓고 길고 구불구불한 통로에서 역추적에 실패한다. (4) 팽창 반경이 통로 반폭보다 작으면 통로 한가운데가 전부 cost 0 이라 경로가 최단으로 칸막이 끝을 스치고, pinky 는 벽면 4.7 cm 까지 붙어 끼인다. 넓은 방 시험으로는 넷 다 드러나지 않는다

## 2026-09-18 · uncommitted · fix(nav): 기동 경쟁과 좁은 방 여유를 실측으로 잡는다
- 변경: 두 코스트맵에 `initial_transform_timeout: 30.0`
- 증거: 2x1 m 데모룸에서 nav2 가 활성화 중 `map→base` TF 를 5.5 s 만 기다리고 포기해 `global_costmap` 활성화가 실패했고 `planner_server` 가 함께 죽었다 — 목표는 `REJECTED` 로 끝나고 로봇은 한 발도 못 뗐다. 그 TF 는 AMCL 이 첫 스캔을 처리한 뒤에 나오는데, RTF 0.3 인 기계에서는 그것이 5 s 를 넘는다
- gate 변화: 없음
- 결정: 없음
- 교훈: 지역화가 늦게 서는 것은 느린 기계의 정상 동작이다. 활성화 대기시간이 그보다 짧으면 스택이 통째로 죽고, 증상은 "목표가 거절됨" 이라 원인과 한참 떨어져 보인다
