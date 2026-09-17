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
    evidence: "soccer + heuristic + MatchHost + HttpPlayerClient mode/teleop/stop (2026-09-18 Windows)"
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
- 심판·휴리스틱·MatchHost 루프는 가짜 Observer/PlayerClient로 LOCAL pytest가 돈다. 빈 `isaac/` 패키지는 제거함.
- `HttpPlayerClient`는 CORE mode/teleop/stop만 부른다. `match --dry-run`은 YAML에서 Field와 두 엔드포인트를 만들고 네트워크를 열지 않는다. 천장 카메라 어댑터는 아직 없다.

## 다음 gate

1. `docs/plans/2026-09-18-rosy-games-local-host.md` Task 9: 문서·경계 시험 마무리 (overhead는 열지 않음).
2. DEVICE/FIELD는 노트북 1v1 실측. 호스트 pytest로 승격하지 않는다.
