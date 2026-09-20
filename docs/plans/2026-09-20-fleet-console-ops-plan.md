# Fleet 콘솔 군집 제어 일치 실행 계획 — D-131 이행

- 작성: 2026-09-20. 근거 ADR: D-131(Accepted, 방향)
- 원칙: **후단이 이미 말하는 것을 전단이 소비하게 한다.** 새 계약은 T6에서만 만들고,
  측정은 T7에서만 한다. 검증은 호스트 pytest + 옵트인 Chromium — DEVICE/FIELD 주장 금지(D-91)

## 0. 백엔드–전단 불일치 장부 (실측)

| 후단이 주는 것 (출처) | 내용 | 전단 현황 | 소비 태스크 |
|---|---|---|---|
| `formation_status.assignment` (console.py:525) | 팔로워별 리더 기준 슬롯(distance·lateral) | 상세 패널 텍스트 요약만, 맵 ✗ | T1 |
| `formation_status.relay.*` (console.py:530) | leader_rx_hz·leader_age_s·follower_tx_hz·connected·paused | leader Hz·paused 텍스트만 — follower_tx_hz·connected·leader_age_s 미소비 | T2 |
| `formation_status.reason`·`pending_triggers` (console.py:528) | HOLD 이유와 대기 트리거 | 상태 태그만(HOLDING 글자), 이유 미소비 | T4 |
| `robots[].queued` (snapshot) | blocked_by·waiting_on·reason | 명렬 텍스트만, 맵 ✗ | T3 |
| `robots[].yielding` + bay (snapshot) | 비켜설 자리·누구 때문 | 명렬 텍스트만, 맵 ✗ | T3 |
| `robots[].goal`·`pose` | 목표·위치 | 맵에 이미 렌더링 ✓ | — |

## T1 대형 슬롯 오버레이 (1단계)

- 대형이 활성인 동안만: 슬롯 좌표 = 리더 pose + 리더 yaw로 회전한 오프셋.
  축·부호 관례는 `fleet/formation/geometry.py` slots()를 구현 전 실측해 따른다
- 요소: 슬롯 고스트(링), 로봇→슬롯 연결선, 추적 오차(m) 표기
- 비활성이면 아무것도 그리지 않는다(§7.3 정상은 안 보임 — 오버레이는 장식이 아니라
  운용자의 현재 작업 대상이다)
- 소유: fleet/server/web. 증거: T5 옵트인 Chromium 시험 + 실서버 시각 확인

## T2 릴레이 건강 → 증거 상태 (1단계)

- 매핑: follower_connected=false → disconnected / RUNNING 중 tx_hz==0 → delayed /
  leader_age_s가 임계 초과 → delayed / 그 외 fresh(무표시). 임계는 상수로 명시하고
  T7 벤치 전까지 보수적으로 둔다
- 위치: 명렬 행 태그 + 맵 로봇 칩. 색은 주의·위험 셋만(D-72), 정상은 무색

## T3 중재 시각화 (1단계)

- queued: 로봇 → blocked_by 로봇 점선 + reason 축약 칩
- yielding: 로봇 → bay 좌표 점선 화살표
- 맵 위 칩은 `--scrim` 바탕 + `--surface-line` 테두리(D-92 오버레이 칩 규칙)

## T4 HOLD 이유 표시 (1단계)

- HOLDING 동안 reason을 맵 위 칩으로, pending_triggers는 명렬 근거 줄로

## T5 검증 (옵트인 Chromium + 실서버)

- `test/test_fleet_console_browser.py` 신설 — 가짜 API 응답(대형 활성 + queued/yielding
  포함)으로 페이지를 띄워 렌더를 단언. **mutation-proven**: 오버레이 코드를 빼면 적색이
  되는지 확인한다(test/ AGENTS 규정 — 적색 확인 없는 게이트는 증거가 아니다)
- 실서버(localhost:8090) Playwright 스크린샷으로 시각 확인
- 증거: `ROSY_RUN_BROWSER_TESTS=1 python -m pytest test/test_fleet_console_browser.py -q`,
  fleet 스위트 회귀 없음

## T6 Robot Selection — 2단계 (FOR-001 파라미터의 구현)

- `formation_start(leader, members)` — 미선택 로봇은 개별 미션을 받을 수 있다
- 새 계약이 아니라 FOR-001이 이미 이름댄 **Robot Selection** 파라미터의 구현이다.
  FLEET SRS 구현 상태 표기를 갱신한다
- D-89 준수: D-35 메커니즘(릴레이 HOLD 모델·대형 후보)은 열지 않는다
- fleet 스위트: 선택 편성 계약 시험(미선택 로봇 goal 허용, 선택 로봇 goal 거절)
- 선행: T1–T5 착지

## T7 N 상한 게이트 — 3단계

- 가짜 로봇 N=5·10·20 HTTP 스텁으로 gather p95를 측정하는 벤치 스크립트 → 수치를
  logs에 기록하고 규모 상한의 인용 원천으로 삼는다. 숫자 없이 규모를 주장하지 않는다

## 순서와 규칙

- T1→T2→T3→T4→T5가 1단계다. 각 태스크 종료 시 logs.md 항목 + index 재생성
- 호스트 pytest만으로 DEVICE/FIELD를 주장하지 않는다(D-91) — 실제 대형 주행 증거는
  D-83 시뮬 재실행과 현장이 소유한다
