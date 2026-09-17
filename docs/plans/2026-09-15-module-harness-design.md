# 모듈 하네스 문서 체계 설계

작성일: 2026-09-15

상태: 설계 제안(P0). ADR D-61 후보(Proposed) — 승인 전에는 기존 규칙이 유효하다. 코드·기존 문서는 아직 바꾸지 않았다.

관련: [ADR Log](../reference/ROSY%20ADR%20Log.md) D-17, D-45 · [폴더 구조 정리](2026-09-13-folder-structure-governance.md) · [모듈 평가·유지보수 설계](2026-09-12-rosy-os-module-evaluation-maintenance-design.md) · [solutions](../solutions/AGENTS.md)

## 1. 왜 필요한가

에이전트가 매 세션 같은 맥락을 다시 찾고, 기록은 쌓이지만 "지금 이 모듈이 어디까지 왔는가"에 답하는 문서가 없다. 2026-09-15 조사 결과:

| 현상 | 근거 |
|---|---|
| AGENTS.md 정체 | git 추적 96개 중 70개가 `Updated: 2026-09-02`. `src/rosy_core/AGENTS.md`에 D-58 readiness, D-60 swarm, control sensor adapter가 없다 |
| 진행 상태 분산·중복 | 작업 폴더 루트 `progress.md`·`task_plan.md`는 git 밖이며 09-13 항목이 두 번씩 들어 있다. 실제 상태는 `*-results.md`(최근 7일 32회 수정), Device 검증 계획, 정리 계획 말미 follow-up에 흩어져 있다 |
| 모듈 스냅샷 부재 | 모듈 상태를 알려면 `docs/plans/`의 날짜별 문서 70여 개를 읽어야 한다 |
| ADR 단일 파일 비대 | 109KB·1,555줄. `test_network_topology_contracts.py`가 본문 ID의 인덱스 누락과 대체 ADR 원문 보존만 확인하며, ID 연속·모듈 연결은 검사하지 않는다. `Accepted; Pi acceptance pending`처럼 결정 상태와 검증 상태가 섞여 있다 |
| 강제 장치 부재 | AGENTS 내용을 보는 시험은 `test/test_control_absorption_package.py` 하나. 문서 lint CI, 프로젝트 hook 없음 |

결론: 기록이 부족한 것이 아니라 **문서별 역할·쓰기 규칙·검사가 없어 drift와 중복이 생긴다.** 모든 폴더에 파일을 늘리면 AGENTS.md 정체가 그대로 반복된다.

## 2. 문서 역할과 권위

| 파일 | 역할 | 쓰기 규칙 | 권위 |
|---|---|---|---|
| `docs/spec/`, `docs/reference/` API | 요구사항·공개 계약 | 기존 D-17/D-18 | 계약 |
| `docs/adr/D-NNN-*.md` | 결정과 이유 | 불변. 변경은 새 ID + `superseded_by` | 계약 |
| `<module>/progress.md` | 현재 gate 스냅샷 | **덮어쓰기**, 본문 길이 제한 | 상태 기준 |
| `<module>/logs.md` | 시간순 작업 기록 | **추가만**, 월 단위 `logs/YYYY-MM.md`로 이동 | 역사 |
| `<module>/index.md` | 모듈 관련 ADR·plan·solution·test 목록 | **생성만**, 수기 편집 금지 | 파생물 |
| `AGENTS.md` | 지도와 작업 규칙 | 느리게, 사람이 다듬음 | 안내 |
| `docs/solutions/**` | 반복 금지 교훈 | 추가(`ce-compound`) | 참고 |

충돌 시 **계약(SRS/API/ADR) > progress.md > logs.md > AGENTS.md** 순으로 따른다. 이는 작업 폴더 루트 AGENTS.md의 "findings/progress는 계약이 아니다" 규칙을 모듈 단위로 옮긴 것이다.

`docs/plans/`의 날짜별 설계·실행·결과 문서는 그대로 유지한다. 단, 진행 상태의 최신값은 plan 말미에 덧붙이지 않고 해당 모듈 `progress.md`에 쓰며, plan에는 링크만 남긴다.

## 3. 적용 단위 (결정: 모듈 수준만)

`progress.md`·`logs.md`·`index.md`는 책임자와 증거 gate가 있는 단위에만 둔다.

- `src/<package>/` 14개: bringup, control, core, description, emotion, fleet, gz_sim, imu_bno055, interfaces, lamp_control, led, navigation, omx_adapter, sensor_adc
- `deploy/`, `dock/`, `docs/`(ADR·plan 운영 자체), 저장소 루트(전 모듈 집계 `STATUS.md`)

하위 폴더(예: `src/rosy_core/rosy_core/safety/`)는 AGENTS.md만 유지한다. 논리 모듈 M01–M14와의 연결은 frontmatter `logical_modules`로 한다. 패키지와 논리 모듈은 1:1이 아니다.

작업 폴더 루트(`Rosy/`)는 git 밖이므로 기준 기록을 두지 않는다.

## 4. 스키마

### 4.1 progress.md

```markdown
---
module: rosy_core
logical_modules: [M03, M04, M07, M11, M13]
owner: CORE
last_verified: { commit: "084b93c", date: 2026-09-15 }   # 커밋은 따옴표 필수 (YAML 숫자 해석 방지)
gates:
  SOURCE:   { state: GO,   evidence: "747 passed, 10 skipped", cmd: "PYTHONPATH=src/rosy_core:src/rosy_control:src python3 -m pytest src/rosy_core/test -q" }
  ROS-SIM:  { state: GO,   evidence: "ROS 출력 시험 10개" }
  ARTIFACT: { state: HOLD, blocker: "signed native ARM64 manifest" }
  DEVICE:   { state: HOLD, blocker: "Pi install + device-readback.sh --json" }
  FIELD:    { state: PARKED }
adrs: [D-1, D-2, D-38, D-58, D-60]
---
## 지금 상태
(15줄 이하)
## 다음 gate
## 현재 유효한 금지사항
```

- gate 키는 기존 어휘 `SOURCE / LOCAL / ROS-SIM / ARTIFACT / DEVICE / FIELD` 여섯 개를 모두 쓰고, 값은 `GO / HOLD / PARKED / N/A`만 허용한다. 빠뜨린 키와 제외한 키를 구분하기 위해 생략은 오류다.
- `GO`에는 `evidence`와 재실행 가능한 `cmd`가 필수, `HOLD`에는 `blocker`가 필수다. 과거 증거를 재실행 없이 옮길 때는 `GO`가 아니라 `HOLD`(blocker: 재실행 필요)로 쓴다.
- 미커밋 작업 트리에서 검증했으면 `last_verified.commit`에 `uncommitted`를 쓰고, lint는 커밋 후 재검증하라는 경고를 낸다. 실행하지 못한 확인은 `GO`로 쓰지 않는다([관련 교훈](../solutions/workflow-issues/inability-to-check-recorded-as-clean-result.md)).
- `N/A`는 평가 프로파일에서 사전에 제외한 경우만 쓴다(모듈 평가 설계 §4).

### 4.2 logs.md 항목

```markdown
## 2026-09-15 · 084b93c · docs(fabric): record hub-slice completion gates
- 변경: ...
- 증거: `python3 -m pytest src/rosy_fleet/test -q` 42 passed   ← 미실행이면 "미실행: 이유"
- gate 변화: 없음 | SOURCE HOLD→GO
- 결정: D-59 참조 | 없음
- 교훈: solutions/... | 없음
```

제목 줄(`날짜 · 커밋 · 요약`)은 파일 안에서 유일해야 한다. 커밋 전에 쓰는 항목은 커밋 칸에 `uncommitted`를 쓴다. 추가만 허용하므로 나중에 해시로 고치지 않으며, 해당 커밋은 `git log -- <module>/logs.md`로 찾는다. 여러 모듈을 건드린 커밋은 각 모듈에 해당 모듈 관점의 한 항목만 쓰고, 공통 내용은 루트 로그에 쓴다.

### 4.3 ADR 파일 (결정: 개별 파일 분리)

```markdown
---
id: D-60
title: 추종은 navigation이 아니라 swarm 패키지다
status: Accepted            # Proposed | Accepted | Superseded | Withdrawn | Reserved
date: 2026-09-15
supersedes: []
superseded_by: []
modules: [rosy_core, rosy_navigation, rosy_fleet]
gates_pending: []           # 예: [DEVICE]
---
**Context:** ...
**Decision:** ...
**Consequences:** ...
```

- 경로: `docs/adr/D-060-follow-is-swarm-not-navigation.md`. 세 자리 번호는 파일 정렬용이며 `id`·제목·본문 참조는 기존 표기 `D-60`을 유지한다.
- 혼합 상태는 분리한다: `Accepted; Pi acceptance pending` → `status: Accepted` + `gates_pending: [DEVICE]`.
- 결번: D-29는 `Withdrawn`(사용하지 않은 번호, vision shield 설계의 제안 표기와 연결), D-35는 `Reserved`(swarm formation sim bench 실측 대기).
- **호환 조건:** `docs/reference/ROSY ADR Log.md`는 36개 문서에서 링크되고 `test/test_network_topology_contracts.py`가 본문을 읽는다. 그러므로 이 파일은 삭제하지 않고, 인덱스 표 + 전체 본문을 번호순으로 이어 붙인 **생성 파일**로 유지한다. 생성 결과는 기존 시험이 쓰는 형태를 지켜야 한다: 본문 제목 `## D-n 제목`, 인덱스 행 `| D-n | 제목 | Status |`, 대체된 ADR의 Status·Context·Decision 원문. 머리말에 "생성물, `docs/adr/`를 편집할 것"을 표시한다.

### 4.4 index.md (생성)

모듈 `index.md`는 **명시적 참조만** 모은다: `progress.md`의 `adrs`·`plans`, frontmatter `modules`에 모듈을 둔 plan, `module:`이 일치하는 solution, `harness.yaml`의 시험 경로, 최근 logs 5건. 본문 경로 언급으로 추정하지 않는다. 추정하면 다른 세션이 plan을 추가할 때마다 생성물 검사가 깨지기 때문이다(P1에서 결정). ADR 분리(P2) 전에는 ADR `modules` 태그가 없으므로 `progress.md`의 `adrs`만 쓴다. ADR은 ID와 제목만 넣고 Status는 넣지 않는다. 다른 세션의 Proposed→Accepted 변경이 무관한 모듈 index를 stale로 만들지 않게 하기 위해서다. plan에는 선택적으로 다음 frontmatter를 추가한다.

```yaml
---
modules: [rosy_core, deploy]
kind: design | execute | results | research
supersedes: []
---
```

## 5. 순환과 강제

```
시작  AGENTS 체인(루트→모듈) + progress.md + index.md + solutions에서 module 검색
 ↓
작업
 ↓
종료  logs.md 추가 → gate 변화 시 progress.md 덮어쓰기
      → 결정이면 ADR Proposed 초안 → 교훈이면 /ce-compound
 ↓
검사  tools/harness (pytest 계약 + CI + hook)
```

### 5.1 도구 `tools/harness/` (ROS-free Python)

- `generate`: 모듈 `index.md`, 루트 `STATUS.md`(전 모듈 gate 표), `ROSY ADR Log.md`를 생성한다. 결정적 출력(정렬 고정, 생성 시각 미포함)이어야 lint에서 비교할 수 있다.
- `lint`:
  - progress frontmatter 스키마, `GO`→evidence / `HOLD`→blocker 필수
  - `last_verified.commit` 이후 모듈 경로 커밋 수가 임계값 초과 시 경고, AGENTS.md `Updated`도 같은 방식
  - logs.md: 제목 중복·잘못된 날짜 금지, `origin/main` merge-base(또는 `HARNESS_BASE_REF`)와 HEAD에 커밋된 내용이 앞부분으로 보존되어야 함. base가 없으면(shallow clone) 경고를 내고 HEAD만 비교한다. CI의 기본 `fetch-depth: 1`에서는 base가 HEAD와 같아 커밋된 수정을 잡지 못하므로 P4에서 PR base 또는 `fetch-depth: 0`을 설정한다(월 이동 커밋은 예외 표시)
  - ADR: ID 연속(Withdrawn/Reserved 포함), 인덱스↔파일 일치, `supersedes`/`superseded_by` 양방향, `modules`가 실제 모듈을 가리킴
  - 생성 파일이 `generate` 결과와 다르면 실패

### 5.2 강제 경로

1. `test/test_harness_contracts.py`: 저장소 관례대로 계약 시험으로 lint를 호출한다. 오래됨 경고는 초기에 xfail이 아닌 경고 출력만 하고, 스키마·중복·ADR 일치는 실패로 한다.
2. `.github/workflows/ci.yml`: 기존 host pytest 단계에 포함된다.
3. 프로젝트 `.claude/settings.json` hook: SessionStart에서 `rosy_harness.py brief`로 등록 모듈 전체의 gate 요약과 기록 순서를 주입한다(구현됨). Stop 알림은 두지 않는다. Stop hook이 차단하면 대화가 반복되고, 차단하지 않으면 모델에 전달되지 않기 때문이다. logs 누락은 계약 시험·CI의 lint가 잡는다. `Rosy OS`를 작업 디렉터리로 연 세션에서만 적용된다. Codex 등은 AGENTS.md 진입점만으로 같은 규칙을 따르며, `src/rosy_control/CLAUDE.md`는 AGENTS.md 포인터로 줄인다.

## 6. 실행 단계

| 단계 | 내용 | 완료 판단 |
|---|---|---|
| P0 | 이 설계 + ADR D-61 Proposed | 스키마·권위 순서 승인 |
| P1 파일럿 | `src/rosy_core`, `deploy`에 progress/logs/index, `tools/harness` generate/lint, 계약 시험 | 도구 시험 통과, 실제 작업 한 사이클 기록 |
| P2 ADR 분리 | `docs/adr/` 이관 스크립트, 생성 Log가 기존 본문과 의미상 동일함을 diff로 확인, D-29/D-35 정리 | `test_network_topology_contracts.py` 포함 기존 시험 통과, 링크 검사 통과 |
| P3 전개 | 나머지 모듈. 작업 폴더 루트 `progress.md`·`task_plan.md`의 중복을 제거해 `rosy_control`·`rosy_core`·`deploy` logs로 이관하고 원본은 archive. 로컬 잔재 `docs/plans/.omc/`(ignore됨) 제거. 정체 AGENTS는 lint 목록 순으로 갱신 | `STATUS.md` 생성, 스키마 오류 0 |
| P4 강제 | CI·hook 활성화, logs 월 이동 자동화 | PR에서 lint가 실제로 막는다 |

## 7. 선행 조건과 비범위

- P2 이전에 현재 커밋되지 않은 `docs/reference/ROSY ADR Log.md`, `docs/*/AGENTS.md` 변경이 커밋되어야 한다. 이관 스크립트가 WIP를 덮어쓰면 안 된다.
- 이 체계는 기록 구조다. ARTIFACT/DEVICE/FIELD gate를 통과시키지 않으며, 기존 HOLD/PARKED 판정을 바꾸지 않는다.
- 요구사항 ID(D-17), API 경로·스키마 단일 소스(D-18)는 변경하지 않는다.
