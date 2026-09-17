# docs logs

추가만 한다. 형식: [module harness 설계](plans/2026-09-15-module-harness-design.md) §4.2.
2026-09-15 이전 이력은 `docs/reference/ROSY ADR Log.md`, `docs/plans/`의 날짜별 문서, `git log -- docs`를 본다.

## 2026-09-15 · uncommitted · docs(harness): start the docs harness pilot
- 변경: `progress.md`, `logs.md` 추가
- 증거: `python tools/harness/rosy_harness.py lint` 0 errors, 2 warnings(rosy_core·deploy last_verified uncommitted, docs 자체 오류 아님); `python -m pytest test/test_network_topology_contracts.py test/test_harness_contracts.py -q` 64 passed (2026-09-15 Windows). `docs` 경로에 미커밋 변경이 있어(`git status --short -- docs` 비어 있지 않음) `last_verified.commit`은 `uncommitted`
- gate 변화: 없음. SOURCE/LOCAL GO, ROS-SIM/ARTIFACT/DEVICE/FIELD N/A(문서 모듈, 실행 대상 없음)를 처음 기록
- 결정: D-61 Proposed
- 교훈: 없음

## 2026-09-15 · uncommitted · docs(harness): register docs and correct generated-file wording
- 변경: `harness.yaml`에 `docs` 등록, `AGENTS.md`에 기록 위치·계약 시험 명령 추가, `progress.md`에서 생성물 범위를 `index.md`·`STATUS.md`로 정정하고 `cmd`를 `python3`으로
- 증거: 미실행 — 기록 정정만. 등록 후 검증은 이어지는 generate·lint 실행으로 확인
- gate 변화: 없음
- 결정: 없음
- 교훈: 없음

## 2026-09-16 · uncommitted · docs(harness): hold docs while the ADR log carries a conflict marker
- 변경: 2차 리뷰 반영. 다른 세션 merge-aside 복원이 `ROSY ADR Log.md` 1590행에 충돌 종료 표시를 남겼고, lint가 충돌 표시를 오류로 잡도록 바뀌므로 lint 기반 증거를 쓰는 SOURCE/LOCAL을 HOLD로. 표시는 다른 세션 소유 작업이라 이 기록에서 고치지 않았다
- 증거: `Select-String -Path "docs/reference/ROSY ADR Log.md" -Pattern '^(<<<<<<<|=======|>>>>>>>)( |$)'` → 1590행 (2026-09-16 01:10)
- gate 변화: SOURCE GO→HOLD, LOCAL GO→HOLD
- 결정: 없음
- 교훈: 없음

## 2026-09-17 · uncommitted · docs(concept): fix interface design laws and per-surface grammar as D-72
- 변경: `docs/concept/16_ROSY_Interface_Design_Principles.md` 신규. ADR Log에 D-72 표 행·본문 추가(Proposed). concept README의 Document Index와 Current mapping 표에 16행 등록. 2026-09-16이 기록한 ADR Log 1590행 충돌 종료 표시가 해소되어 SOURCE/LOCAL 재판정
- 증거: `python tools/harness/rosy_harness.py lint` 0 errors, 16 warnings; `python -m pytest test/test_network_topology_contracts.py test/test_harness_contracts.py -q` 69 passed (2026-09-17 Windows, 미커밋 WIP 포함 작업 트리). 이 호스트의 python3에는 PyYAML이 없어 `python`(3.14.5)으로 실행했다. 1590행 재확인: 충돌 표시 없음, D-61 본문 산문
- gate 변화: SOURCE HOLD→GO, LOCAL HOLD→GO (blocker 해소). ROS-SIM/ARTIFACT/DEVICE/FIELD는 N/A 유지
- 결정: D-72 Proposed. D-68(CAP-001과 개념 descriptor 분리)과 D-71(합성 미구현)은 유지하며 뒤집지 않는다. 콘솔 통합(두 서버·CSP·단일 파일 자족성)과 D-7/D-23 상태 불일치는 이 기록이 결정하지 않는다
- 교훈: 없음

## 2026-09-17 · uncommitted · docs(adr): supersede D-7 so the local screen has one standing decision
- 변경: ADR Log에 D-75 표 행·본문 추가(Proposed). D-7 표 행과 본문 Status를 `Superseded by D-75`로. `docs/progress.md`의 `adrs`에 D-75 추가하고 다음 gate 3번을 해소로 표시. 계획 문서 `docs/plans/2026-09-17-interface-design-implementation-design.md` 신규(pending approval, 범위 A 확정)
- 증거: `python tools/harness/rosy_harness.py lint` 0 errors, 16 warnings; `python -m pytest test/test_network_topology_contracts.py test/test_harness_contracts.py -q` 69 passed (2026-09-17 Windows, 미커밋 WIP 포함 작업 트리)
- gate 변화: 없음. SOURCE/LOCAL GO 유지
- 결정: D-75 Proposed — D-7(React+TS+Vite)을 대체하고 로봇 로컬 화면을 빌드 단계 없는 손으로 쓴 정적 자산으로 확정한다. D-23이 사실상 대체해 왔으나 두 ADR이 모두 Accepted로 남아 모순이었다
- 교훈: Accepted ADR 둘이 서로 모순인 채로 한 달 넘게 남아 있었고, 구현은 한쪽을 따르고 문서는 양쪽을 주장했다. 이행 계획을 세우는 단계에서야 드러났다 — 새 결정이 기존 결정을 실질적으로 대체할 때 Status 갱신을 같은 커밋에서 하지 않으면 이런 모순이 조용히 남는다

## 2026-09-17 · 8fdd8d2 · docs: lock G4 vocabulary, one operator console, and D-61 records
- 변경: concept 16 어휘 정정, D-77, D-61 Accepted, 모듈 progress/logs와 생성 index 착륙
- 증거: `python tools/harness/rosy_harness.py lint`; `python -m pytest test/test_network_topology_contracts.py test/test_harness_contracts.py test/test_control_launch_boundary.py -q`
- gate 변화: 없음. SOURCE/LOCAL GO 유지. DEVICE N/A
- 결정: D-61 Accepted, D-77 Accepted
- 교훈: 없음

## 2026-09-17 · uncommitted · docs(adr): lock leftover gates as D-78–D-81
- 변경: 남은 HOLD를 새 ADR로 가름. D-78 네이티브 Pi ARTIFACT, D-79 현재 트리 GO, D-80 G4는 Device, D-81 Fleet REST gather. device-validation §1 ROS-SIM을 HOLD로 정정
- 증거: `python -m pytest test/test_network_topology_contracts.py test/test_harness_contracts.py -q`
- gate 변화: 없음. docs SOURCE/LOCAL GO. ARTIFACT/DEVICE는 소비 모듈 HOLD
- 결정: D-78–D-81 Accepted (경로·증거 규칙). G0–G3는 D-41–D-56 Proposed 유지
- 교훈: 없음

