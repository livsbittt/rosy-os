# signal logs

추가만 한다. 형식: [module harness 설계](../docs/plans/2026-09-15-module-harness-design.md) §4.2.

## 2026-09-21 · uncommitted · feat(signal): ROSY-SIGNAL-001 계약 초안 + ESP32 참조 펌웨어
- 변경: `signal/` 신설 — `README.md`(계약 초안), `firmware/rosy_signal/rosy_signal.ino`
  (페일세이프 상태기계 참조 구현), `AGENTS.md` 3건, `progress.md`, `logs.md`,
  `test/test_signal_contract.py` 14건, 하니스 등록(`tools/harness/harness.yaml`)
- 증거: `python -m pytest test/test_signal_contract.py -q` 14 passed (2026-09-21
  Windows, Python 3.14). 부팅 모드 변이 외에 누락돼 있던 `modeName` 정의와 Wi-Fi
  SSID/키 분리를 적색 시험으로 재현한 뒤 수정했다. Arduino compile은 미실행
- gate 변화: SOURCE HOLD→GO (계약 시험 신설·통과). LOCAL/ARTIFACT/DEVICE HOLD 신설
- 결정: 없음(ADR 미작성). 설계 근거는
  `docs/plans/2026-09-21-traffic-light-controller-research.md`
- 교훈: SSR(G3MB-202P)은 AC 전용이라 접점 스위칭 용도에 부적합 — 기계식 릴레이로
  확정(조사 보고서 §4). `all_red`(점등)과 `failsafe`(점멸)의 구별이 관제 화면의
  "정지시켰다 vs 장비 고장" 판별을 만든다.

## 2026-09-22 · uncommitted · feat(signal): Fleet G-S3 클라이언트·관제 연동

- 변경: `src/site/fleet/fleet/server/signals.py` 클라이언트와 Fleet API/UI를 연결했다.
  상태 gather, 인증 command, e-stop의 병렬 `all_red`, failsafe 의도 1회 재단언을
  구현하되 로봇 CORE와 교통 안전 판정에는 연결하지 않았다.
- 증거: `python -m pytest src/site/fleet/test -q` 362 passed, 5 skipped;
  `python -m pytest test/test_signal_contract.py -q` 14 passed (2026-09-22 Windows).
- gate 변화: LOCAL HOLD→GO. ARTIFACT/DEVICE는 ESP32 빌드·물리 접점 실측 전까지 HOLD.
- 결정: 신호등은 표시 장치이며 로봇 안전 인터록이 아니라는 기존 경계를 유지한다.
- 교훈: `stale_seq`는 적용 성공이 아니며, 성공 응답도 장치가 failsafe에 남아 있으면
  재단언 예산을 다시 열면 안 된다.
