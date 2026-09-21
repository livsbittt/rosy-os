## D-148 벤치는 fleet이 소유한 공개면(fleet.bench)만 소비한다

**Status:** Accepted (2026-09-21).

**Context:** `gz_sim/scripts/swarm_bench.py`가 `fleet.formation.geometry`와 `fleet.swarm.{robots,session,transport}` 내부 모듈을 직접 import했다. 선언(`gz_sim` package.xml의 `fleet` exec_depend)은 있었으나 실제 결합은 내용 결합이라 fleet 내부 재조정이 시뮬 벤치를 깨뜨릴 수 있었다(결합도 평가 2026-09-19 §6 C등급). 벤치는 "rclpy 없이 fleet만 쓰는" 계측 도구다 — sim → site 방향으로 흐르는 유일한 코드 경로였다.

**Decision:**

1. **fleet이 벤치용 공개면 `fleet.bench`를 소유한다.** `Formation`, `slot_world_position`, `load_robots`, `FormationSession`, `FormationSpec`, `SessionState`, `HttpRobotClient`, `RobotApiError`를 재수출하는 단일 모듈이다.
2. **gz_sim은 `fleet.bench`만 import한다.** `fleet.swarm.*`/`fleet.formation.*` 직접 import 금지를 gz_sim 구조 테스트(`test_bench_boundary.py`)로 고정한다.
3. **fleet 내부 재조정은 이 면의 시그니처만 지키면 된다.** 벤치가 쓰는 이름이 바뀌면 `fleet.bench`에서 별칭으로 흡수한다.

**Alternatives:** 벤치 스크립트를 fleet 패키지로 이전 — Gazebo 자산(장애물 SDF 스폰) 의존이 남아 완전 분리가 되지 않고 시뮬 계측 주기가 함대 릴리스 주기에 묶인다. 시뮬 전용 스텁 격리 — 계측 대상 로직과 스텁이 어긋나면 벤치가 거짓을 계측한다. 현상 유지 — 선언은 있으나 내용 결합이라 fleet 리팩터링이 깨진다.

**Consequences:** 결합은 스탬프(데이터) 수준으로 내려간다. fleet의 공개 API가 하나 늘고, 그 면은 함대 내부 재조정과 무관하게 안정돼야 한다.

**Validation / Transition:** gz_sim 구조 테스트가 scripts/ 전체에서 `fleet.swarm`/`fleet.formation` 직접 import를 금지하고, fleet 테스트가 `fleet.bench` 재수출의 import 가능성을 검증한다. `python3 -m pytest src/sim/gz_sim/test/test_bench_boundary.py src/site/fleet/test/test_bench_facade.py -q`.

**References:** 결합도 평가 §7-4 (2026-09-19), `docs/plans/2026-09-08-swarm-formation-slice-design.md` §8.2, D-147.

---
