<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-17 | Updated: 2026-09-17 -->
# server

## Purpose

관제 PC의 Fleet 서버 v1 — 사이트 오케스트레이터와 관제 UI 역할(site-fabric 설계 §2, 전환
순서 3단계). 등록된 N대의 상태를 모으고, 로봇별 목표·취소와 전체 정지를 내린다. 미션은
Fleet 쪽에 남는다(D-12): 하달한 목표를 기억하는 곳은 여기지 로봇이 아니다.

## Key Files

| File | Description |
|---|---|
| `console.py` | `FleetConsole` — gather(snapshot/map)와 scatter(goal/cancel/estop). 전송은 `swarm.transport` 만 쓴다 |
| `app.py` | FastAPI 표면. `/api/fleet/*` 와 `/console` 정적 자산 allowlist |
| `web/` | 관제 UI (index.html, tokens.css, styles.css, console.js) |

## For AI Agents

- **v1 의 gather 는 폴링이다.** 설계 §3 의 최종 경로는 로봇 `FleetAgent` 의 outbound WS 지만
  그 에이전트는 이 서버가 생긴 뒤에야 소켓을 연다. 붙으면 `snapshot()` 의 출처만 바꾼다.
- 로봇 pose 는 CORE 가 TF `map → <ns>base_footprint` 로 읽어 준 map 프레임 값이다
  (`ros_bridge._map_frame = "map"`). `map` 은 사이트 공유 프레임이라 N대를 한 격자에 겹쳐
  그릴 수 있다 — 로봇별로 `rosy_XX/map` 을 만들면 이 화면도 CORE 의 목표 전달도 깨진다.
- e-stop 은 부분 실패해도 200 이다. 5xx 로 접으면 어느 대가 섰는지 화면이 알 수 없다.
- UI 는 CSP `style-src 'self'` 아래에서 돈다 — `style` 속성과 `el.style.x =` 는 적용되지
  않는다. 색과 배치는 클래스로만 준다.
- 이 서버는 robots.yaml 의 운영자 토큰을 들고 있다. 기본 바인드는 루프백이고, 밖으로 열려면
  `--token` 이 필수다(`cli.run_console` 가 강제).
- 로봇 로컬 대시보드를 대체하지 않는다. 한 대의 현장 화면·수동 조작·비상정지는 CORE
  `/dashboard` 에 그대로 있다(D-23).

## Testing Requirements

`src/rosy_fleet/test/test_server_console.py`, `test_server_app.py` — 가짜 로봇만 쓰고
네트워크는 없다. `test_server_app.py` 는 `fastapi.testclient` 를 쓰므로 fastapi 가 필요하다.
