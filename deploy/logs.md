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

## 2026-09-21 · 1acb41a · feat(deploy): fail-closed Pinky commissioning

- 변경: G0-G5 순차 세션, 실제 release/readback JSON 유도, 증거 SHA-256,
  lock/CAS 원자 저장, SSH/console 런북, 유선/무선 인터페이스 검증 추가
- 증거: `python -m pytest test -q` -> 1001 passed, 13 skipped; 집중 169개,
  Python/Bash/PowerShell 구문 및 `git diff --check` 통과
- gate 변화: SOURCE/LOCAL GO 갱신. ARTIFACT/DEVICE는 signed ARM64 bundle과
  실제 Pinky Pro readback 전까지 HOLD, FIELD는 N/A 유지
- 결정: 없음
- 교훈: G0-G2는 작업자 요약이 아니라 stage manifest/install/readback 원문에서
  유도하고, G3-G5 미측정 템플릿은 검증을 통과하지 못해야 한다
