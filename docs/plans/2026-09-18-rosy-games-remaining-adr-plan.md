# 남은 rosy_games 트랙 → ADR 계획

작성일: 2026-09-18
상태: D-95–D-111. 계단 프리셋과 첫 접촉 0.10 상한까지. 현장 GO가 아니다.

관련: D-90, D-91, D-94 ·
[game host 설계](2026-09-17-robot-soccer-game-host-design.md) ·
[LOCAL 호스트](2026-09-18-rosy-games-local-host.md) ·
[overhead](2026-09-18-rosy-games-overhead-plan.md)

## 1. Goal

축구 **규칙 엔진은 따로** 두고, Rosy가 아직 안 닫은 호스트 일을 **순서 있는 ADR**로
고정한다. D-90(집)·D-94(노트북 OpenCV ≠ D-41)를 반복하지 않는다.

이 계획이 웹캠을 열거나, Pinky를 달리게 하거나, Isaac 폴더를 만들지 않는다.

## 2. 남은 일 ↔ ADR

| 남은 일 | ADR | 다음에 할 실행 |
|---|---|---|
| 합성 overhead pytest를 DEVICE GO로? | **D-95** | 아니요. `--observer hold`가 기본 |
| 실기 천장 1v1 순서 | **D-96** | 카메라만 → 한 대 0.08 → 두 대 이격 → 저속 1v1 → 킥오프 반복 |
| 계단 1이 달리면? | **D-107** | 기본 관측만. `--observe-only` |
| 계단 2+ 드라이브? | **D-108** | `--drive` / `--drive rosy_01`. FIELD GO 아님 |
| YAML을 0.20으로? | **D-110** | 아니요. linear ≤ 0.10 |
| 계단을 CLI로? | **D-111** | `--stair 1–5` 프리셋. FIELD GO 아님 |
| 온보드 앞 카메라 지금? | **D-97**, **D-109** | 아니요. observer 카탈로그에 없음 |
| Isaac / `isaac/` 폴더 | **D-98**, **D-109** | 아니요. 폴더 없음 |
| 신경망을 cmd_vel에? | **D-99**, **D-109** | 아니요. `neural` 거절 |
| Fleet 매치 버튼 | **D-106** | 지금은 안 만듦. 생기면 Fleet→`reset()` 한 방향 |
| games를 D-62 슬라이스로? | D-90, **D-106** | 아니요 |
| D-41을 overhead로 닫기 | D-94 | 아니요 |
| 골대를 QR/영역으로 보이게 | **D-100** | ArUco 20/21 + 선택 HSV 입구. 득점은 m 폴리곤 |
| 경기 화면을 CORE 콘솔에? | **D-101** | 아니요. 노트북 `rosy_games --preview` |
| 매치가 1틱 뒤 죽나? | **D-102** | `--ticks` 없으면 20 Hz, Ctrl+C까지 |
| YAML angular·lost_hold 미사용? | **D-103** | angular는 gate 클램프. HOLD는 즉시. period ≤ lost_hold_s |
| 첫 접촉을 CORE limits에? | **D-104** | arm 때 PUT `/safety/limits` |
| 스페이스 정지? | **D-105** | CLI 스페이스 + 보드 `POST /stop` → 양쪽 halt |

## 3. 새 ADR 요약

| ID | 결정 |
|---|---|
| D-95 | 합성 천장 프레임 ≠ DEVICE. 기본 observer는 `hold` |
| D-96 | 현장 다섯 계단. 충돌 속도는 그 기기 안전 증거 다음 |
| D-97 | 온보드는 FIELD 반복 뒤, CMD-001 후보, D-41을 닫지 않음 |
| D-98 | Isaac 폴더는 FIELD 반복 전 없음. Gazebo는 축구 체육관이 아님 |
| D-99 | 학습 정책은 `Policy.act`만. 최종 `cmd_vel` 금지 |
| D-100 | 골 위치는 ArUco 20/21 + 영역. 일반 QR 아님. 호모그래피는 코너 |
| D-101 | 축구 보드는 노트북 게임 표면. CORE `/dashboard` 금지 |
| D-102 | `--ticks` 없으면 20 Hz 루프. preview는 보드만 |
| D-103 | limits는 gate. 유실 HOLD 즉시. period ≤ lost_hold_s |
| D-104 | arm은 MANUAL 다음 PUT safety/limits |
| D-105 | 스페이스·보드 /stop은 양쪽 safety/stop. 보드는 CORE를 직접 안 침 |
| D-106 | Fleet 매치 시작은 나중. 지금 버튼 없음. fleet↛games import |
| D-107 | 계단 1 기본은 관측만. arm/teleop 없음 |
| D-108 | `--drive`는 계단 2+. 한 id면 그 대만. FIELD GO 아님 |
| D-109 | 카탈로그는 soccer/heuristic/hold/overhead만. onboard/isaac/neural 거절 |
| D-110 | 첫 접촉 linear ≤ 0.10. 0.20은 계단 4 기록 다음 |
| D-111 | `--stair 1–5` 호스트 프리셋. pytest ≠ FIELD GO |

## 4. 실행 순서 (다음 세션)

1. `--stair 1 --observer overhead --preview` (D-111, D-107). 실제 웹캠
2. 기기 안전 증거 뒤 `--stair 2 --drive rosy_01 --observer overhead --preview`
3. `--stair 3` 이격 → `--stair 4` 1v1 → `--stair 5` 킥오프 반복
4. 계단 4가 여러 번 나온 뒤에만 D-97 온보드, D-98 Isaac, D-99 신경망. 0.20은 그 다음 ADR

**하지 않음** — 합성 pytest로 FIELD GO, 기본 CLI가 `/dev/video0`을 염, `isaac/`을 지금 만듦, 온보드 blob이 `cmd_vel`을 냄, D-41 Status를 Accepted로 올림.

## 5. 수락

- ADR 로그에 D-95–D-111 색인·본문이 있다
- `python -m pytest test/test_harness_contracts.py src/rosy_games/test test/test_rosy_games_surface.py -q`
