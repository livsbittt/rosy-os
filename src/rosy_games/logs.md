# rosy_games logs

추가만 한다. 형식: [module harness 설계](../../docs/plans/2026-09-15-module-harness-design.md) §4.2.

## 2026-09-18 · uncommitted · feat(games): load a match config without touching the robots

- 변경: `config/match.yaml` + `load_match()` + `rosy_games match --config ... --dry-run`. Field와 두 `RobotEndpoint`만 만들고 HTTP를 열지 않는다. `match.local.yaml`은 gitignore.
- 증거: `python -m pytest src/rosy_games/test test/test_rosy_games_surface.py -q`
- gate 변화: 없음 (LOCAL GO 유지)

## 2026-09-18 · uncommitted · feat(games): talk to CORE with mode, teleop, and stop only

- 변경: `HttpPlayerClient`가 CORE `POST /api/v1/mode`·`/teleop`·`/safety/stop`만 부른다. 4xx/5xx는 예외. `MatchHost._estop_all`은 한쪽 `estop` 실패 후에도 나머지를 호출한다.
- 증거: `python -m pytest src/rosy_games/test test/test_rosy_games_surface.py -q`
- gate 변화: 없음 (LOCAL GO 유지)

## 2026-09-18 · uncommitted · feat(games): run the match loop against fake robots

- 변경: `MatchHost`가 `Observer.observe` → `game.step` → `policy.act` → `gate` → `PlayerClient.teleop`/`estop`. 킥오프 미준비·유실 HOLD도 roster 양쪽에 teleop 0. `teleop` 예외면 양쪽 `estop`. TwistSink 제거.
- 증거: `python -m pytest src/rosy_games/test test/test_rosy_games_surface.py -q`
- gate 변화: 없음 (LOCAL GO 유지)

## 2026-09-18 · uncommitted · feat(games): policy returns twists for both robots

- 변경: `Policy.act(obs, state) -> dict[str, Twist]`. 휴리스틱은 PLAY에서 관측된 두 로봇 모두에 추적·골 바이어스·이격을 내고, 그 외 phase는 빈 dict. MatchHost.tick이 dict를 gate에 넘긴다.
- 증거: `python -m pytest src/rosy_games/test test/test_rosy_games_surface.py -q`
- gate 변화: 없음 (LOCAL GO 유지)

## 2026-09-18 · uncommitted · feat(games): clamp non-play and ramming twists in the referee gate

- 변경: `game/gate.py`가 PLAY가 아니면 ZERO, 0.35 m 이내면 전진 linear를 `min(linear, 0)`, NaN/inf는 ZERO. `Field.min_spacing_m=0.35`. MatchHost.tick이 gate를 거친다.
- 증거: `python -m pytest src/rosy_games/test test/test_rosy_games_surface.py -q`
- gate 변화: 없음 (LOCAL GO 유지)

## 2026-09-18 · uncommitted · chore(games): bootstrap pytest path and drop empty isaac

- 변경: `test/conftest.py`로 루트 pytest 수집. 빈 `rosy_games/isaac/` 삭제. harness 기록 추가
- 증거: `python -m pytest src/rosy_games/test test/test_rosy_games_surface.py -q`
- gate 변화: SOURCE/LOCAL HOLD로 기록 시작. ROS-SIM/ARTIFACT N/A, DEVICE/FIELD PARKED
