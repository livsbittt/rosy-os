# 남은 rosy_games 트랙 → ADR 계획

작성일: 2026-09-18
상태: D-95–D-99. LOCAL 호스트·합성 천장 프레임은 있다. 현장 1v1 GO가 아니다.

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
| 온보드 앞 카메라 지금? | **D-97** | 아니요. 계단 4 반복 뒤 CMD-001 |
| Isaac / `isaac/` 폴더 | **D-98** | 계단 4 반복 전 금지. env는 `game`만 |
| 신경망을 cmd_vel에? | **D-99** | 아니요. `Policy` 플러그인 |
| Fleet 매치 버튼 | D-90 | 버튼은 Fleet, `reset()`은 games. 지금 구현하지 않음 |
| games를 D-62 슬라이스로? | D-90 | 아니요 |
| D-41을 overhead로 닫기 | D-94 | 아니요 |

## 3. 새 ADR 요약

| ID | 결정 |
|---|---|
| D-95 | 합성 천장 프레임 ≠ DEVICE. 기본 observer는 `hold` |
| D-96 | 현장 다섯 계단. 충돌 속도는 그 기기 안전 증거 다음 |
| D-97 | 온보드는 FIELD 반복 뒤, CMD-001 후보, D-41을 닫지 않음 |
| D-98 | Isaac 폴더는 FIELD 반복 전 없음. Gazebo는 축구 체육관이 아님 |
| D-99 | 학습 정책은 `Policy.act`만. 최종 `cmd_vel` 금지 |

## 4. 실행 순서 (다음 세션)

1. **기록 (이 커밋)**
2. 노트북에서 `--observer overhead` — 모터 없이 구장·공·로봇이 안정적으로 보이는지 (D-96 계단 1)
3. 그 기기 정지·워치독·단일 `cmd_vel` 증거가 있으면 한 대 0.08 m/s (계단 2)
4. 두 대 이격 → 저속 1v1 → 킥오프 반복 (계단 3–5)
5. 계단 4가 여러 번 나온 뒤에만 D-97 온보드, D-98 Isaac, D-99 신경망

**하지 않음** — 합성 pytest로 FIELD GO, 기본 CLI가 `/dev/video0`을 염, `isaac/`을 지금 만듦, 온보드 blob이 `cmd_vel`을 냄, D-41 Status를 Accepted로 올림.

## 5. 수락

- ADR 로그에 D-95–D-99 색인·본문이 있다
- `python -m pytest test/test_harness_contracts.py src/rosy_games/test test/test_rosy_games_surface.py -q`
