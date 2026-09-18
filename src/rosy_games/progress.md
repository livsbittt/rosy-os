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
    evidence: "76 passed including 20 Hz live loop and angular clamp (2026-09-18 Windows)"
    cmd: "python -m pytest src/rosy_games/test test/test_rosy_games_surface.py -q"
  ROS-SIM:
    state: N/A
  ARTIFACT:
    state: N/A
  DEVICE:
    state: PARKED
  FIELD:
    state: PARKED
adrs: [D-90, D-94, D-95, D-96, D-97, D-98, D-99, D-100, D-101, D-102, D-103]
plans:
  - docs/plans/2026-09-17-robot-soccer-game-host-design.md
  - docs/plans/2026-09-18-rosy-games-local-host.md
  - docs/plans/2026-09-18-rosy-games-overhead-plan.md
  - docs/plans/2026-09-18-rosy-games-remaining-adr-plan.md
---
## 지금 상태

- 노트북 게임 호스트 (D-90). CORE 모드 아님. 최종 `cmd_vel` 없음.
- LOCAL 호스트: 플러그인 심판 + HoldObserver 또는 `--observer overhead`. `--ticks` 없으면 20 Hz (D-102). `--preview`는 보드만 (D-101). limits는 gate (D-103).
- DEVICE/FIELD는 실제 천장 웹캠·마커 실측. 합성 프레임 pytest로 승격하지 않는다.

## 다음 gate

1. D-96 계단 1: 실제 웹캠 `--observer overhead`, 모터 없음, 코너·로봇·공·골 20/21
2. 그 기기 정지·워치독·단일 publisher 뒤 계단 2–5
3. 계단 4 반복 뒤에만 D-97 온보드, D-98 Isaac, D-99 신경망
