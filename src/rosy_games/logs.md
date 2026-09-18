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

## 2026-09-18 · uncommitted · docs(games): mark LOCAL host complete without overhead camera

- 변경: 경계 시험이 field/game/policy에서 cv2/httpx/rclpy/rosy_core/rosy_fleet을 금지하고, host는 overhead.py만 cv2를 허용한다. loop.py/transport.py는 cv2 없음. LOCAL 호스트를 overhead 없이 닫음.
- 증거: `python -m pytest src/rosy_games/test test/test_rosy_games_surface.py -q` 31 passed
- gate 변화: LOCAL GO 유지. SOURCE는 트리에서 overhead/homography를 다음 계획으로 명시한 채 GO. DEVICE/FIELD PARKED.

## 2026-09-18 · uncommitted · feat(games): plug soccer in and arm CORE without a camera

- 변경: `catalog`로 soccer/heuristic 플러그인. `match.local.yaml` 오버레이. `HoldObserver`+`run_match`로 카메라 없이 MANUAL 무장·정지 teleop. 관측 예외 시 양쪽 halt. 빈 토큰은 Authorization 생략.
- 증거: `python -m pytest src/rosy_games/test test/test_rosy_games_surface.py -q` 42 passed
- gate 변화: 없음. LOCAL GO 유지. DEVICE/FIELD PARKED.

## 2026-09-18 · uncommitted · feat(games): project the ceiling camera onto the pitch

- 변경: `field/homography.py` 순수 호모그래피. `host/project.py` 픽셀→Observation. `host/overhead.py`만 cv2 (ArUco 코너 10–13, 로봇 마커, 주황 blob). CLI `--observer overhead|hold`.
- 증거: `python -m pytest src/rosy_games/test test/test_rosy_games_surface.py -q` 53 passed
- gate 변화: LOCAL GO 유지 (합성 프레임). DEVICE/FIELD PARKED.

## 2026-09-18 · uncommitted · docs(adr): remaining games track is D-95–D-99

- 변경: progress `adrs`에 D-94–D-99. 다음 게이트는 D-96 계단 1
- 증거: ADR 로그 색인
- gate 변화: 없음. DEVICE/FIELD PARKED

## 2026-09-18 · uncommitted · docs(adr): D-100 goal markers

- 변경: progress `adrs`에 D-100. 골 20/21 + 영역
- 증거: ADR 로그
- gate 변화: 없음

## 2026-09-18 · uncommitted · feat(games): see goals as ArUco 20/21 (D-100)

- 변경: `match.yaml` `goals.home_id`/`away_id`(기본 20/21), 선택 HSV 입구. overhead가 마커·영역을 필드 m 폴리곤으로 투영. 양쪽 없으면 필드 끝 기하. 득점은 `in_home_goal`/`in_away_goal`. cv2는 overhead만.
- 증거: `python -m pytest src/rosy_games/test test/test_rosy_games_surface.py -q` 64 passed
- gate 변화: LOCAL GO 유지 (합성). DEVICE/FIELD PARKED

## 2026-09-18 · uncommitted · docs(adr): D-101 games board is not CORE dashboard

- 변경: progress `adrs`에 D-101. 축구 보드는 노트북 게임 표면
- 증거: ADR 로그
- gate 변화: 없음

## 2026-09-18 · uncommitted · feat(games): serve a laptop match board off CORE (D-101)

- 변경: `rosy_games/web/` 정적 보드. `--preview`가 127.0.0.1에서 overlay JSON·선택 JPEG. CORE `/dashboard`·tokens.css 없음. cv2는 overhead만.
- 증거: `python -m pytest src/rosy_games/test test/test_rosy_games_surface.py -q` 69 passed
- gate 변화: LOCAL GO 유지. DEVICE/FIELD PARKED

## 2026-09-18 · uncommitted · fix(games): keep --preview open until interrupt

- 변경: `--preview`이고 `--ticks`가 없으면 20 Hz로 Ctrl+C까지. 프레임 유실 시 JPEG를 비움. dry-run에 `goals 20/21`. 보드는 home_id로 색을 가름.
- 증거: `python -m pytest src/rosy_games/test test/test_rosy_games_surface.py -q` 72 passed
- gate 변화: 없음. LOCAL GO 유지. DEVICE/FIELD PARKED

## 2026-09-18 · uncommitted · docs(adr): D-102 20 Hz loop, D-103 yaml limits

- 변경: progress `adrs`에 D-102·D-103
- 증거: ADR 로그
- gate 변화: 없음

## 2026-09-18 · uncommitted · feat(games): run live matches at 20 Hz and clamp yaml limits (D-102, D-103)

- 변경: `--ticks` 없으면 20 Hz Ctrl+C. `--preview`는 보드만. `limits.angular`는 gate·휴리스틱 클램프. 유실 HOLD는 즉시. period > lost_hold_s면 기동 거부.
- 증거: `python -m pytest src/rosy_games/test test/test_rosy_games_surface.py -q` 76 passed
- gate 변화: LOCAL GO 유지. DEVICE/FIELD PARKED

## 2026-09-18 · uncommitted · docs(adr): D-104 limits PUT, D-105 halt input

- 변경: progress `adrs`에 D-104·D-105
- 증거: ADR 로그
- gate 변화: 없음

## 2026-09-18 · uncommitted · feat(games): arm PUT limits and halt on space or board stop (D-104, D-105)

- 변경: arm이 MANUAL 다음 PUT `/safety/limits`. 스페이스와 보드 POST `/stop`이 양쪽 halt. 보드는 CORE URL을 열지 않음.
- 증거: `python -m pytest src/rosy_games/test test/test_rosy_games_surface.py -q` 79 passed
- gate 변화: LOCAL GO 유지. DEVICE/FIELD PARKED
