# 완전 모듈 분리 실행 계획 (D-126)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 설계 [2026-09-19-full-module-separation-design.md](2026-09-19-full-module-separation-design.md) 의 이음새 S0~S5를 닫는다.
끝 상태는 가드 5개가 모두 초록이다. 동작은 바꾸지 않는다.

**Architecture:** 가드 먼저(S0), 작은 이음새(S2·S3·S4), 큰 이음새(S1·S5) 순.
S1은 D-63이 예고한 토픽 경계 이행이며 D-64의 `ALLOWED` 집합을 비운다.

**Tech Stack:** Python 3.12, AST 기반 계약 시험, 새 의존성 없음.

**이 계획이 아닌 것:** `core_features` 추가 분할, 멀티 프로세스, mapping 분리, 이미지·compose 변경.

**Windows:** `Rosy OS` 루트. `python`으로 실행한다. 커밋: `type(scope): 무엇을 왜`.

---

## File Structure (목표)

| 파일 | 책임 |
|---|---|
| `test/test_module_separation.py` | S0~S5 가드 5개 (신 경로 기준). 구 `test_runtime_slices.py`의 D-64 검사를 대체한다 |
| `src/apps/control/control/web_node.py` | S2: 최종 `cmd_vel` 구독 제거 |
| `src/apps/control/control/wander/node.py` | S2: 최종 `cmd_vel` 구독 제거 |
| `src/site/fleet/package.xml` | S3: `exec_depend: core` → `core_common` (+ `test_depend: core_features`) |
| `src/sim/gz_sim/package.xml` | S4: `fleet`(유지 확인) + `navigation` `exec_depend` 선언으로 고정 |
| `src/core/core/core/bridge/control_sensor_adapter.py` | S1: `control.*` import 3건 제거, 증거 토픽 구독으로 전환 |
| `src/core/core_api_web/core_api_web/api/deps.py` | S5: features 접근 파사드 |
| `src/core/core_api_web/core_api_web/api/v1/*.py` | S5: `core_features.*.manager` 직접 참조를 `deps` 경유로 |

---

### Task 0: 가드 재건 — 신 경로에서 5개 이음새를 잠근다

**Files:** Create `test/test_module_separation.py`

가드 5개 (전부 AST·문자열 검사, ROS 불필요):

1. `test_core_imports_no_slice_code`: `src/core/**` 생산 코드에 `control/fleet/bringup/navigation/emotion/omx_adapter/games` import 0건. 지금은 S1 때문에 FAIL.
2. `test_control_has_no_final_cmd_vel`: `src/apps/control/**` 생산 코드에 `'cmd_vel'`·`"cmd_vel"` 정확 일치 0건. 지금은 S2 2곳 때문에 FAIL. (`cmd_vel_raw`는 허용 — 정규식으로 단어 경계를 맞춘다.)
3. `test_package_xml_covers_imports`: 19개 `package.xml`의 의존 집합이 같은 패키지의 코드 import 집합을 덮는다. 지금은 S1(`core`→`control` 미선언) 때문에 FAIL.
4. `test_cmd_vel_single_publisher`: `Twist, "cmd_vel"`/`'cmd_vel'` 발행이 `src/core/core/core/bridge/ros_bridge.py` 1곳뿐. 지금 PASS (잠금).
5. `test_fleet_prod_only_core_common`: `src/site/fleet` 비테스트 코드의 `core_*` 참조는 `core_common`만. 지금 PASS (잠금).

- [ ] **Step 1:** 파일 생성. 1·2·3은 FAIL, 4·5는 PASS를 확인한다.
- [ ] **Step 2 (mutation-prove):** 가드마다 지키는 대상을 일부러 깨고 빨강을 확인한 뒤 복원한다
  (예: adapter에 `import control.foo` 한 줄 추가 → 가드 1 빨강).
  빨강을 보지 못한 가드는 커밋하지 않는다.
- [ ] **Step 3:** `python -m pytest test/test_module_separation.py -q` — 2 passed, 3 failed가 기대값이다.
- [ ] **Step 4: Commit:** `git add test/test_module_separation.py && git commit -m "test(deps): lock five module seams on the new layout"`

---

### Task 1: S2 — control의 최종 `cmd_vel` 구독 잔재 제거

**Files:** `src/apps/control/control/web_node.py:431`, `src/apps/control/control/wander/node.py:36`

- [ ] **Step 1:** 가드 2가 빨강임을 확인 (Task 0에서 이미).
- [ ] **Step 2:** 두 구독을 세션·원시 계열로 옮긴다. 운영 토픽명(`cmd_vel`)을 소비하지 않게 한다.
  발행이 아니라 구독이므로 로봇 동작은 그대로이나, 토픽명 공유가 단일 발행자(D-2) 추론을 깨뜨린다.
  `control/safety/node.py:88`의 레거시 비교 그래프 발행자 기본값은 parity 계약(`test_os_control_graph.py`)이
  고정하므로 유지하고, 가드 2에 정확히 1곳으로 핀한다.
- [ ] **Step 3:** `python -m pytest test/test_module_separation.py::test_control_has_no_final_cmd_vel src/apps/control/test -q` PASS.
- [ ] **Step 4:** 관련 control 회귀 전체 PASS. 운영 launch에 두 노드가 최종 토픽으로 묶이지 않음을 `launch/` grep으로 확인.
- [ ] **Step 5: Commit:** `git commit -m "refactor(control): stop subscribing to the final cmd_vel"`

---

### Task 2: S3 — fleet 선언을 실제(`core_common`)로 축소

**Files:** `src/site/fleet/package.xml`

- [ ] **Step 1:** `exec_depend: core` → `exec_depend: core_common`. 시험만 쓰는 `core_features.swarm`
  (`test_geometry.py`)을 위해 `test_depend: core_features` 추가.
- [ ] **Step 2:** `python -m pytest test/test_module_separation.py::test_package_xml_covers_imports -q`
  — S1이 남아 여전히 FAIL이어야 한다 (S3 단독으로 초록이 되면 가드가 거짓말이다).
- [ ] **Step 3:** `python -m pytest src/site/fleet/test -q` PASS.
- [ ] **Step 4: Commit:** `git commit -m "refactor(fleet): depend on core_common, not the whole core"`

---

### Task 3: S4 — gz_sim의 fleet·navigation 참조를 선언으로 고정

**Files:** `src/sim/gz_sim/package.xml`

`swarm_bench.py`의 존재 이유가 fleet 세션을 시뮬에서 돌리는 것이므로 import 자체는 유지한다.
닫을 것은 미선언 상태뿐이다: `fleet`은 이미 선언되어 있고, `launch/gz_multi.launch.py`의
`navigation.frame_prefix` import에 `exec_depend: navigation`을 추가한다.
시뮬→함대/내비는 하향 의존이라 허용한다 (D-126이 금지하는 것은 CORE의 상향·횡단 import다).

- [ ] **Step 1:** `package.xml`에 `exec_depend: navigation` 추가 (위 edit 완료).
  `fleet` 선언은 유지한다.
- [ ] **Step 2:** `python -m pytest src/sim/gz_sim/test test/test_module_separation.py::test_package_xml_covers_imports -q`
  — 가드 3 위반에서 gz_sim 항목이 사라졌는지 확인 (S1·S5 항목은 Task 4·5까지 잔류).
- [ ] **Step 3: Commit:** `git commit -m "refactor(sim): declare the fleet/navigation deps the sim already uses"`

---

### Task 4: S1 — 어댑터를 토픽 경계로 (D-64 `ALLOWED`를 비운다)

**Files:** `src/core/core/core/bridge/control_sensor_adapter.py`, `test/test_module_separation.py`

가장 큰 작업이므로 쪼갠다:

- [ ] **Step 1:** `control.calibration_snapshot` 로드(`:118`)를 파일 스냅샷 리더 경유로 바꾼다.
  calibration digest·generation 검증 의미 유지.
- [ ] **Step 2:** `control.safety.node.SafetyNode`(`:140`) sensor-only 생명주기 검사를
  노드 공개 속성 프로브(duck-type, D-64 방식 유지)로 바꾼다. import 없이 검사한다.
- [ ] **Step 3:** `control.control.command_gate.CommandPolicy`(`:213`) 생성을 증거 토픽
  (`TranslationEvidence`·`TrackedEvidence` 수신) 소비로 바꾼다. 정책 교체 시 무효화 유지.
- [ ] **Step 4:** `ALLOWED_ROSY_CONTROL`에 해당하는 구 가드 상수를 신 가드에서 삭제한다.
  가드 1·3이 PASS해야 한다: `python -m pytest test/test_module_separation.py -q` 5 passed.
- [ ] **Step 5:** `src/core/core/test` + `src/apps/control/test` 전체 PASS.
- [ ] **Step 6: Commit:** `git commit -m "refactor(core): sensor adapter consumes evidence topics, not control code"`

각 Step마다 기존 `test_control_sensor_adapter.py` 계열이 PASS해야 한다. 깨지면 Step을 더 쪼갠다.

---

### Task 5: S5 — api_web은 `deps`만 본다

**Files:** `src/core/core_api_web/core_api_web/api/deps.py`, `api/v1/*.py` 12개

- [ ] **Step 1:** `deps.py`에 features 접근자(`command_arb()`, `nav_manager()`, `dock_db()`,
  `diag_collector()`, `map_store()`, `swarm_mgr()`, `waypoints_mgr()`)를 둔다.
- [ ] **Step 2:** 라우터 파일을 하나씩 옮긴다. 한 파일당: 옮기기 → 해당 api 시험 PASS → 다음.
- [ ] **Step 3:** AST 검사(신규 가드 6 또는 기존 가드 확장): `api/v1/*.py`에 `core_features.` 직접 참조 0건.
- [ ] **Step 4: Commit:** `git commit -m "refactor(api): route feature access through deps facade"`

---

### Task 6: 회귀와 ADR 수용

- [ ] **Step 1:** `python -m pytest test/test_module_separation.py test/ -q` PASS.
  `src/core/core/test`, `src/apps/control/test`, `src/site/fleet/test`,
  `src/apps/omx_adapter/test`, `src/apps/games/test` PASS (Windows는 rclpy 불필요 분만).
- [ ] **Step 2:** 설계 문서 상태를 "구현 완료"로 한 줄 갱신. D-126 Status Proposed→Accepted는
  5개 가드 초록 + 위 회귀가 모두 있어야 한다. 하나라도 빠지면 Proposed 유지.
- [ ] **Step 3:** `docs/logs.md`에 항목 추가, gate 변화가 있으면 `docs/progress.md` 갱신.

---

## 완료 판정

- 가드 5개 초록 + 가드 6(S5) 초록.
- `grep -rn "from control\|import control" src/core --include=*.py` 0건 (주석 제외).
- 최종 `cmd_vel` 발행 1곳, `control`의 최종 토픽 참조 0건.
- DEVICE/ARTIFACT/FIELD gate는 변하지 않는다. 이 계획은 SOURCE/LOCAL 증거만 만든다.
