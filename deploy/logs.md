# deploy logs

추가만 한다. 형식: [module harness 설계](../docs/plans/2026-09-15-module-harness-design.md) §4.2.
2026-09-15 이전 이력은 [Device 검증 계획](../docs/plans/2026-09-13-rosy-os-device-validation-implementation-plan.md)과 `git log -- deploy`를 본다.

## 2026-09-15 · uncommitted · docs(harness): start the deploy harness pilot
- 변경: `progress.md`, `logs.md`, 생성 `index.md` 추가. `AGENTS.md`에 기록 위치와 작업 순서 연결
- 증거: `python -m pytest test -q` 835 passed, 12 skipped (Windows + Git Bash/OpenSSL PATH, 미커밋 WIP 포함 작업 트리)
- gate 변화: 없음. 기존 SOURCE/LOCAL GO, ARTIFACT/DEVICE HOLD를 스냅샷으로 옮김
- 결정: D-61 Proposed
- 교훈: 없음

## 2026-09-15 · uncommitted · docs(harness): state excluded gates and rerunnable source evidence
- 변경: 리뷰 반영. ROS-SIM·FIELD를 N/A로 명시(물리 구동은 소비 모듈 gate), SOURCE에 재실행 명령 추가, `last_verified.commit`을 `uncommitted`로
- 증거: 미실행 — 기록 형식만 변경
- gate 변화: 없음 (누락 키를 N/A로 명시)
- 결정: 없음
- 교훈: 없음

## 2026-09-18 · uncommitted · feat(host-agent): structured network status, set_mode, connect (D-124)

- 변경: network.status 를 D-26 필드로 파싱. network.set_mode, network.connect 허용. PSK는 감사/응답에서 제거
- 증거: `python -m pytest test/test_host_agent.py -q`
- gate 변화: 없음. DEVICE HOLD 유지
- 결정: D-124
- 교훈: 없음
