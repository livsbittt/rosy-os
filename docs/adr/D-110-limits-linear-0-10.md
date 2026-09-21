## D-110 첫 접촉 limits.linear는 0.10을 넘지 않는다

**Status:** Accepted (2026-09-18). 호스트 속도 상한이다. 0.20 m/s FIELD GO가 아니다.

**Context:** D-96은 첫 접촉을 0.08–0.10 m/s로 두고, 프로필 0.20은 그 기기 안전
증거와 계단 4 반복 다음이다. `match.yaml` `limits.linear`를 0.20으로 올리면
호스트 gate가 그대로 CORE에 밀어 넣는다 (D-103, D-104).

**Decision:**

- `load_match`는 `limits.linear` > **0.10** 이면 거부한다
- 기본 0.08은 그대로다
- 0.20은 계단 4 기록이 있는 **다음 ADR**에서만 연다
- 이 상한이 DEVICE 워치독 증거를 대신하지 않는다

**Alternatives:** YAML만 믿고 0.20을 허용하는 안은 계단을 건너뛴다. 0.08만
허용하는 안은 설계의 0.08–0.10 구간을 자른다.

**Consequences:** `FIRST_CONTACT_LINEAR_M = 0.10`. 현장 속도 올리기는 별도 결정.

**Validation / Transition:** `test_cli.py` load_match. DEVICE/FIELD PARKED.

**References:** D-96, D-103, D-104.

---
