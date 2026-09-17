---
module: rosy_games
logical_modules: []
owner: GAMES
last_verified: { commit: "uncommitted", date: 2026-09-18 }
gates:
  SOURCE:
    state: GO
    evidence: "package.xml, 경계 시험, 이미지·슬라이스 미포함. 설계 §3.1에서 overhead.py·homography.py만 다음 계획으로 미룸 (2026-09-18 Windows)"
    cmd: "python -m pytest src/rosy_games/test/test_games_boundaries.py test/test_rosy_games_surface.py -q"
  LOCAL:
    state: GO
    evidence: "31 passed, 카메라 없이 득점·이격·쌍정지·dry-run. overhead/homography 없음 (2026-09-18 Windows)"
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
- LOCAL 호스트 닫힘: 심판·휴리스틱·MatchHost·HttpPlayerClient·`match --dry-run`. `isaac/` 없음. `host/overhead.py`와 `field/homography.py`는 만들지 않음.
- DEVICE/FIELD는 천장 카메라 실측. 호스트 pytest로 승격하지 않는다.

## 다음 gate

1. DEVICE/FIELD: 천장 카메라 실측 계획 (`overhead.py` / `homography.py`). 호스트 pytest로 승격하지 않는다.
