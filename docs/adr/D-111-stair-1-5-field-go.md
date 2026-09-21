## D-111 `--stair 1–5`는 호스트 프리셋이며 FIELD GO가 아니다

**Status:** Accepted (2026-09-18). D-96 계단의 CLI 매핑이다. 현장 GO가 아니다.

**Context:** 계단 2는 한 대, 3–5는 두 대다. `--drive`만 있으면 실수가 두 대를
계단 2로 연다. `--stair` 없이 현장 순서를 기억하면 건너뛰기 쉽다.

**Decision:**

- `--stair 1` 관측만. `--drive`와 같이 쓰지 않는다
- `--stair 2`는 `--drive <한 id>`가 필요하다 (한 대)
- `--stair 3|4|5`는 두 대. `--drive`가 없으면 둘 다 연다. 한 id만 주면 거부
- `--stair`는 overhead를 강제하지 않는다. 기본 observer는 여전히 hold (D-95)
- `--stair N` pytest 통과 ≠ 그 계단 FIELD GO (D-91, D-96)
- 킥오프(계단 5)는 계속 사람이 공을 둔다. 호스트는 중앙 공 전에는 PLAY로 넘기지
  않는다 (이미 SoccerGame)

**Alternatives:** 계단 번호를 문서에만 두는 안은 CLI가 두 대를 계단 2로 연다.
`--stair 2`가 첫 로봇을 추측하는 안은 yaml 순서를 드라이브 명단으로 승격한다.

**Consequences:** 현장 명령은 `--stair 1 --observer overhead --preview` 다음
`--stair 2 --drive rosy_01 --drive`가 아니라 `--stair 2 --drive rosy_01`.

**Validation / Transition:** `test_cli.py`. FIELD PARKED.

**References:** D-91, D-95, D-96, D-107, D-108.

---
