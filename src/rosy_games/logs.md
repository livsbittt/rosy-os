# rosy_games logs

추가만 한다. 형식: [module harness 설계](../../docs/plans/2026-09-15-module-harness-design.md) §4.2.

## 2026-09-18 · uncommitted · feat(games): clamp non-play and ramming twists in the referee gate

- 변경: `game/gate.py`가 PLAY가 아니면 ZERO, 0.35 m 이내면 전진 linear를 `min(linear, 0)`, NaN/inf는 ZERO. `Field.min_spacing_m=0.35`. MatchHost.tick이 gate를 거친다.
- 증거: `python -m pytest src/rosy_games/test test/test_rosy_games_surface.py -q`
- gate 변화: 없음 (LOCAL GO 유지)

## 2026-09-18 · uncommitted · chore(games): bootstrap pytest path and drop empty isaac

- 변경: `test/conftest.py`로 루트 pytest 수집. 빈 `rosy_games/isaac/` 삭제. harness 기록 추가
- 증거: `python -m pytest src/rosy_games/test test/test_rosy_games_surface.py -q`
- gate 변화: SOURCE/LOCAL HOLD로 기록 시작. ROS-SIM/ARTIFACT N/A, DEVICE/FIELD PARKED
