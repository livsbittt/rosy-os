## D-109 계단 4 전 카탈로그는 soccer/heuristic/hold/overhead만이다

**Status:** Accepted (2026-09-18). D-97·D-98·D-99의 호스트 잠금이다. 온보드·Isaac·
신경망을 지금 구현하지 않는다.

**Context:** D-97은 온보드를 계단 4 뒤에 두고, D-98은 `isaac/`을 만들지 않으며,
D-99는 `NeuralPolicy`를 카탈로그 등록 전에 파일을 만들지 말라고 했다. CLI
`--observer`가 문자열 분기로만 있으면 `--onboard`가 다음 패치에 섞이기 쉽다.
overhead를 catalog가 모듈 상단에서 import하면 cv2가 hold 경로까지 올라온다.

**Decision:**

- `GAMES` = `{soccer}`, `POLICIES` = `{heuristic}`, `OBSERVERS` = `{hold, overhead}`
- `make_observer("onboard")` / `make_policy("neural")` / `make_game` 미등록 이름은
  ValueError
- `host/onboard.py`, `policy/neural.py`, `isaac/`을 지금 만들지 않는다
- `make_observer`는 overhead를 **쓸 때만** import한다. catalog 모듈 로드가 cv2를
  끌어오지 않는다
- 온보드가 열려도 `Observer` 플러그인이다. `cmd_vel`을 내지 않는다 (D-97, D-99)
- 이 잠금이 D-41·D-52를 Accepted로 올리지 않는다

**Alternatives:** 지금 onboard 스텁을 두는 안은 빈 isaac과 같다. catalog가
overhead를 항상 import하는 안은 hold pytest에 cv2가 필요해진다.

**Consequences:** CLI `--observer` 선택지는 카탈로그에서 온다.

**Validation / Transition:** `test_catalog.py`, `test_rosy_games_surface.py`.
D-41 행은 Proposed. DEVICE/FIELD PARKED.

**References:** D-41, D-94, D-96, D-97, D-98, D-99.

---
