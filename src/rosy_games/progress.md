---
module: rosy_games
logical_modules: []
owner: GAMES
last_verified: { commit: "uncommitted", date: 2026-09-18 }
gates:
  SOURCE:
    state: GO
    evidence: "package.xml, 경계 시험, 이미지·슬라이스 미포함 (2026-09-18 Windows)"
    cmd: "python -m pytest src/rosy_games/test/test_games_boundaries.py test/test_rosy_games_surface.py -q"
  LOCAL:
    state: GO
    evidence: "soccer + heuristic + MatchHost + HTTP mode/teleop/stop + dry-run CLI (2026-09-18 Windows)"
    cmd: "python -m pytest src/rosy_games/test test/test_rosy_games_surface.py -q"
  ROS-SIM:
    state: N/A
  ARTIFACT:
    state: N/A
  DEVICE:
    state: PARKED
  FIELD:
    state: PARKED
adrs: [D-90]
plans:
  - docs/plans/2026-09-17-robot-soccer-game-host-design.md
  - docs/plans/2026-09-18-rosy-games-local-host.md
---
## 지금 상태

- 노트북 게임 호스트 (D-90). CORE 모드 아님. 최종 `cmd_vel` 없음.
- 심판·휴리스틱·MatchHost 스켈레톤은 있음. 빈 `isaac/` 패키지는 제거함.
- HttpPlayerClient는 mode/teleop/stop만. 천장 카메라 어댑터는 없다.

## 다음 gate

1. 천장 카메라 관측 어댑터 (overhead) — 이 LOCAL 계획 밖.
2. DEVICE/FIELD는 노트북 1v1 실측. 호스트 pytest로 승격하지 않는다.
