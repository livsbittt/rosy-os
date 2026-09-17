# rosy_gz_sim logs

추가만 한다. 형식: [module harness 설계](../../docs/plans/2026-09-15-module-harness-design.md) §4.2.
2026-09-15 이전 이력은 [군집 대형 슬라이스 결과](../../docs/plans/2026-09-08-swarm-formation-slice-results.md)와 `git log -- src/rosy_gz_sim`를 본다.

## 2026-09-15 · uncommitted · docs(harness): start the rosy_gz_sim harness record
- 변경: `progress.md`, `logs.md` 추가
- 증거: `python -m pytest src/rosy_gz_sim/test -q` 1 skipped (2026-09-15 Windows, ROS 2 `launch` 패키지 없어 `pytest.importorskip`로 전체 skip — 증거 아님)
- gate 변화: 없음. SOURCE/LOCAL/ROS-SIM을 HOLD로, ARTIFACT/DEVICE/FIELD를 N/A(aarch64에서 `return()`, Pi 이미지 미포함)로 처음 기록
- 결정: D-61 Proposed
- 교훈: 없음

## 2026-09-17 · uncommitted · feat(sim): host-contract for world_to_map
- 변경: CMake에 world_to_map.py install. harness functional에 test_world_to_map.py. SOURCE/LOCAL을 launch skip에서 정답 맵 시험으로 옮김
- 증거: `python -m pytest src/rosy_gz_sim/test/test_gz_package_contract.py src/rosy_gz_sim/test/test_world_to_map.py -q` 8 passed (2026-09-17 Windows)
- gate 변화: SOURCE HOLD→GO, LOCAL HOLD→GO. ROS-SIM HOLD 유지
- 결정: D-79 — launch skip은 증거가 아니다
- 교훈: 없음

## 2026-09-17 · uncommitted · feat(sim): 어려운 월드·정답 맵 생성기·맵을 만들며 주행하는 모드
- 변경: `worlds/rosy_maze.world`(뱀형 통로 + 0.55 m 문 + 막다른 주머니), `worlds/rosy_swarm_bench.world`(6x6 열린 방 + 비대칭 기둥), `scripts/world_to_map.py`(월드 기하 → nav2 점유 격자), `gz_multi` 에 `mode:=slam_nav`·`spawn_x/spawn_y`·`inflation_radius` 인자, 카메라 `always_on` 0 / 10 Hz, `test/test_world_to_map.py` 6건
- 증거: `python -m pytest src/rosy_gz_sim/test -q` 11 passed, 1 skipped (Windows). 실환경: `mode:=slam_nav` 로 공장을 주행하며 재매핑해 8/8 목표 ARRIVED, free 2808 → 3737 셀. 카메라 수정 전후 RTF 0.07 → 1.0 (단일 로봇, 같은 기계)
- gate 변화: 없음(커밋 뒤 재실행으로 판정)
- 결정: 없음
- 교훈: 좁은 통로 월드는 맵핑이 순환에 걸린다 — 맵이 없으면 nav2 를 못 쓰고, nav2 없이 몰면 벽에 끼고, 끼면 바퀴가 헛돌아 odom 이 폭주하고, 그 odom 으로 뜬 맵은 못 쓴다. `slam_nav`(맵 작성 + 주행)와 정답 맵 생성기가 각각 그 고리를 끊는다. 그리고 구독자 없는 1280x720 카메라 하나가 소프트웨어 렌더러에서 RTF 를 14배 깎았다 — D-34 가 말하는 "구독자가 없으면 보내지 않는다" 는 성능 문제이기도 하다
