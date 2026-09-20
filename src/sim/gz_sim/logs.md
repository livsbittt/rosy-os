# gz_sim logs

추가만 한다. 형식: [module harness 설계](../../docs/plans/2026-09-15-module-harness-design.md) §4.2.
2026-09-15 이전 이력은 [군집 대형 슬라이스 결과](../../docs/plans/2026-09-08-swarm-formation-slice-results.md)와 `git log -- src/gz_sim`를 본다.

## 2026-09-15 · uncommitted · docs(harness): start the gz_sim harness record
- 변경: `progress.md`, `logs.md` 추가
- 증거: `python -m pytest src/gz_sim/test -q` 1 skipped (2026-09-15 Windows, ROS 2 `launch` 패키지 없어 `pytest.importorskip`로 전체 skip — 증거 아님)
- gate 변화: 없음. SOURCE/LOCAL/ROS-SIM을 HOLD로, ARTIFACT/DEVICE/FIELD를 N/A(aarch64에서 `return()`, Pi 이미지 미포함)로 처음 기록
- 결정: D-61 Proposed
- 교훈: 없음

## 2026-09-17 · uncommitted · feat(sim): host-contract for world_to_map
- 변경: CMake에 world_to_map.py install. harness functional에 test_world_to_map.py. SOURCE/LOCAL을 launch skip에서 정답 맵 시험으로 옮김
- 증거: `python -m pytest src/gz_sim/test/test_gz_package_contract.py src/gz_sim/test/test_world_to_map.py -q` 8 passed (2026-09-17 Windows)
- gate 변화: SOURCE HOLD→GO, LOCAL HOLD→GO. ROS-SIM HOLD 유지
- 결정: D-79 — launch skip은 증거가 아니다
- 교훈: 없음

## 2026-09-17 · uncommitted · feat(sim): 어려운 월드·정답 맵 생성기·맵을 만들며 주행하는 모드
- 변경: `worlds/rosy_maze.world`(뱀형 통로 + 0.55 m 문 + 막다른 주머니), `worlds/rosy_swarm_bench.world`(6x6 열린 방 + 비대칭 기둥), `scripts/world_to_map.py`(월드 기하 → nav2 점유 격자), `gz_multi` 에 `mode:=slam_nav`·`spawn_x/spawn_y`·`inflation_radius` 인자, 카메라 `always_on` 0 / 10 Hz, `test/test_world_to_map.py` 6건
- 증거: `python -m pytest src/gz_sim/test -q` 11 passed, 1 skipped (Windows). 실환경: `mode:=slam_nav` 로 공장을 주행하며 재매핑해 8/8 목표 ARRIVED, free 2808 → 3737 셀. 카메라 수정 전후 RTF 0.07 → 1.0 (단일 로봇, 같은 기계)
- gate 변화: 없음(커밋 뒤 재실행으로 판정)
- 결정: 없음
- 교훈: 좁은 통로 월드는 맵핑이 순환에 걸린다 — 맵이 없으면 nav2 를 못 쓰고, nav2 없이 몰면 벽에 끼고, 끼면 바퀴가 헛돌아 odom 이 폭주하고, 그 odom 으로 뜬 맵은 못 쓴다. `slam_nav`(맵 작성 + 주행)와 정답 맵 생성기가 각각 그 고리를 끊는다. 그리고 구독자 없는 1280x720 카메라 하나가 소프트웨어 렌더러에서 RTF 를 14배 깎았다 — D-34 가 말하는 "구독자가 없으면 보내지 않는다" 는 성능 문제이기도 하다

## 2026-09-18 · uncommitted · fix(sim): 월드 프로필이 간격을 주도록 하고 공장 팽창을 실측으로 올린다
- 변경: `gz_multi` 의 `spawn_spacing` 기본값 "1.5" → "" (비면 프로필 값), `worlds.yaml` 의 공장 `inflation_radius` 0.15 → 0.25, 데모룸 spawn (-0.5, 0) 간격 1.0
- 증거: 프로필에 `spawn_spacing: 1.0` 을 적어도 런치 기본값 1.5 가 항상 이겨, 2x1 m 데모룸에서 둘째 로봇이 x=1.0 — 벽 안쪽 — 에 spawn 됐다(정답 좌표 0.998). 공장 팽창 0.15 에서는 선반 사이를 지날 때 라이다 최소 거리가 0.08 m 까지 붙었고(풋프린트 반폭 6 cm), 0.25 에서는 같은 목표에 같은 정확도(오차 0.13 m)로 도착하면서 0.20 m 로 벌어졌다
- gate 변화: 없음
- 결정: 없음
- 교훈: 비어 있지 않은 런치 기본값은 프로필을 무력화한다. "인자가 없으면 프로필" 을 하려면 기본값이 비어 있어야 한다

## 2026-09-18 · uncommitted · feat(sim): lock ros_gz_bridge and seed spawn initialpose (D-114, D-115)

- 변경: `gz_multi` 는 domain_bridge/ROS_DOMAIN_ID 없음. `spawn_xy` 와 `seed_initialpose` 가 nav 모드에서 map 시드를 심는다.
- 증거: `python -m pytest src/gz_sim/test -q`
- gate 변화: 없음. ROS-SIM HOLD. pytest ≠ GO

## 2026-09-18 · uncommitted · feat(sim): pin Cyclone and keep images off gz_multi (D-117, D-118, D-120)

- 변경: gz_multi 환경에 rmw_cyclonedds_cpp 와 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST. launch_sim image_bridge 는 기본 꺼짐.
- 증거: `python -m pytest src/gz_sim/test/test_gz_package_contract.py test/test_dds_rmw_contracts.py -q`
- gate 변화: 없음. ROS-SIM HOLD

## 2026-09-20 · uncommitted · fix(sim): stabilize exact-map Nav2 startup and corner geometry

- 변경: defer Nav2/SLAM startup by 15 wall-clock seconds, use non-composed Nav2 for constrained hosts, seed initial pose only in static-nav mode, apply reducing-only narrow-space controller settings, and replace the simulation rectangle with its padded circumscribed radius in both costmaps.
- 증거: exact map loaded with `map_id=occupancy:2646647774c5`, initial pose became fresh, lifecycle nodes became active, and the relevant simulation tests passed `11 passed in 31.69 s`. A repeat goal timed out under shared WSL load 60--90, so it is not a route pass.
- gate 변화: none. ROS-SIM full-route remains HOLD; the run proves startup/localization and exposes a prior yaw-dependent `Start occupied` corner case.
- 교훈: an orientationless global planner must not admit a pose that only the current rectangular yaw can occupy when the controller will need to rotate there.
