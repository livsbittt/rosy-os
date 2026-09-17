# rosy_games logs

추가만 한다. 형식: [module harness 설계](../../docs/plans/2026-09-15-module-harness-design.md) §4.2.

## 2026-09-18 · uncommitted · chore(games): bootstrap pytest path and drop empty isaac

- 변경: `test/conftest.py`로 루트 pytest 수집. 빈 `rosy_games/isaac/` 삭제. harness 기록 추가
- 증거: `python -m pytest src/rosy_games/test test/test_rosy_games_surface.py -q`
- gate 변화: SOURCE/LOCAL HOLD로 기록 시작. ROS-SIM/ARTIFACT N/A, DEVICE/FIELD PARKED

## 2026-09-18 · uncommitted · feat(games): referee, gate, and match loop against fakes
- 변경: Pose2D/Twist, step(obs), HOLD/GOAL, gate 이격, Policy.act dict, MatchHost가 클라이언트 실패 시 양쪽 estop
- 증거: `python -m pytest src/rosy_games/test test/test_rosy_games_surface.py -q` 12 passed
- gate 변화: 없음. DEVICE/FIELD PARKED
- 결정: D-90 LOCAL 호스트 루프. PlayerClient HTTP는 다음
- 교훈: 없음
