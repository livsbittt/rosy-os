## D-104 호스트 arm은 MANUAL 다음에 PUT safety/limits를 건다

**Status:** Accepted (2026-09-18). 호스트 계약이다. DEVICE GO가 아니다.

**Context:** 설계 §4.2와 D-96 계단 2는 첫 접촉을 `PUT /api/v1/safety/limits`로
0.08–0.10 m/s에 묶는다. 호스트 gate(D-103)만 있으면 CORE 프로필 최대 0.20이
그대로다. `HttpPlayerClient`는 mode/teleop/stop만 알았다. PUT limits는 Admin
토큰이다. 같은 토큰으로 403이 나면 `match.local.yaml` 문제이지 PUT을 생략할
이유가 아니다.

**Decision:**

- `MatchHost.arm()`은 각 로봇에 `set_manual` 다음 `PUT /api/v1/safety/limits`
  `{manual_linear, manual_angular}` (match.yaml `limits`)
- `max_linear`가 없으면 PUT하지 않는다 (단위 시험 더블)
- 한쪽 실패는 지금처럼 양쪽 `halt`
- follow / navigation / swarm 경로는 여전히 없다
- 이 PUT이 DEVICE 정지·워치독 증거를 대신하지 않는다 (D-96)

**Alternatives:** gate만 믿는 안은 호스트가 죽으면 워치독 전에 프로필 최대로
달릴 수 있다. 토큰이 operator면 건너뛰는 안은 첫 접촉 속도가 문서와 달라진다.

**Consequences:** `HttpPlayerClient.set_limits`. `test_transport`는 limits를
허용하고 follow/nav/swarm은 계속 금지.

**Validation / Transition:** `test_transport.py`, `test_loop.py`. DEVICE/FIELD PARKED.

**References:** D-90, D-96, D-103, SAF-004,
[API Ref §5](../reference/ROSY%20API%20%26%20Protocol%20Reference.md).

---
