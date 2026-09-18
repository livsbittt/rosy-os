---
module: rosy_games
logical_modules: []
owner: GAMES
last_verified: { commit: "411a303", date: 2026-09-18 }
gates:
  SOURCE:
    state: GO
    evidence: "package.xml, 경계 시험, overhead.py만 cv2. 이미지·슬라이스 미포함 (2026-09-18 Windows)"
    cmd: "python -m pytest src/rosy_games/test/test_games_boundaries.py test/test_rosy_games_surface.py -q"
  LOCAL:
    state: GO
    evidence: "53 passed including synthetic overhead frames (2026-09-18 Windows)"
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
- LOCAL 호스트: 플러그인 심판 + HoldObserver 또는 `--observer overhead`. `field/homography.py`는 cv2 없음. `host/overhead.py`만 OpenCV.
- DEVICE/FIELD는 실제 천장 웹캠·마커 실측. 합성 프레임 pytest로 승격하지 않는다.

## 다음 gate

1. DEVICE/FIELD: 실제 천장 카메라, 네 모서리 ArUco 10–13, 로봇 1/2, 주황 공.
