## D-61 모듈 상태는 progress·logs·생성 index로 기록하고 계약 시험으로 지킨다

**Status:** Accepted (2026-09-17). 기록 구조이며 ARTIFACT/DEVICE/FIELD 판정과
구분한다.

**Context:** AGENTS.md 96개 중 70개가 2026-09-02에서 멈췄다. 진행 상태는 날짜별
plan 말미, `*-results.md`, git 밖 작업 폴더 `progress.md`에 흩어졌고 같은 항목이
두 번 기록됐다. 모듈의 현재 gate를 한 곳에서 읽을 수 없고, 이 ADR Log는 109KB로
커져 인덱스·ID 연속성을 사람이 맞추고 있다.

**Decision:** 책임자와 증거 gate가 있는 모듈(패키지, `deploy`, `dock`, `docs`)은
`AGENTS.md` 옆에 세 기록을 둔다. `progress.md`는 frontmatter gate 스냅샷을 덮어쓰고
(`GO`는 evidence, `HOLD`는 blocker 필수), `logs.md`는 추가만 하며, `index.md`와 루트
`STATUS.md`는 `tools/harness/rosy_harness.py`가 명시적 참조로만 생성한다. 충돌 시
SRS·API·ADR > progress > logs > AGENTS 순이다. 형식과 생성물 최신성, ADR 인덱스·ID
연속성은 `test/test_harness_contracts.py`가 CI의 host pytest에서 확인한다.
하위 폴더는 AGENTS.md만 유지한다.

**Alternatives:** 모든 AGENTS 폴더에 기록을 두는 안은 정체된 AGENTS.md를 세 배로
늘린다. 중앙 파일 하나에 module 태그를 다는 안은 모듈에서 작업하는 에이전트가 자기
상태를 바로 읽지 못한다. 채택하지 않는다.

**Consequences:** 기존 날짜별 plan과 results는 설계·증거 기록으로 남고, 최신 상태만
모듈 `progress.md`로 옮긴다. 이 결정은 기록 구조이며 ARTIFACT/DEVICE/FIELD 판정을
바꾸지 않는다. ADR의 개별 파일 분리는 후속 단계이며, 분리 후에도 이 Log는 전체
본문을 담은 생성 파일로 유지해 기존 링크와 시험을 보존한다.

**Validation / Transition:** `python tools/harness/rosy_harness.py lint` ·
`python -m pytest test/test_harness_contracts.py test/test_network_topology_contracts.py -q`.
harness.yaml 모듈마다 `progress.md`/`logs.md`와 생성 `index.md`가 있다. 루트
`STATUS.md`는 generate만 고친다. last_verified가 `uncommitted`이면 lint 경고.

**References:** [module harness 설계](../plans/2026-09-15-module-harness-design.md), [폴더 구조 정리](../plans/2026-09-13-folder-structure-governance.md).

---
