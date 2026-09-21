## D-103 match.yaml 한계는 게이트 계약이고 유실 HOLD는 즉시다

**Status:** Accepted (2026-09-18). 호스트 안전 계약이다. DEVICE GO가 아니다.

**Context:** `limits.linear: 0.08`은 정책 속도로 들어갔지만 `limits.angular: 0.40`은
YAML에만 있고 휴리스틱은 각속도를 ±1.0까지 낸다. `watchdog.lost_hold_s: 0.5`도
로드만 되고 심판은 유실 즉시 HOLD다. 0.5초를 게임에 디바운스로 넣으면 공을 잃은
뒤에도 마지막 teleop가 남는다. 설계는 유실 즉시 양쪽 정지고, 500 ms는 CORE
워치독(SAF-002)이다.

**Decision:**

- `limits.linear` / `limits.angular`는 **gate의 마지막 클램프**다. 정책이 더 크게
  내도 호스트가 잘라 낸다
- 휴리스틱도 같은 한계를 존중한다. gate가 없으면 안 된다
- 유실 HOLD는 **즉시**다. `lost_hold_s`를 디바운스로 쓰지 않는다
- `lost_hold_s`는 CORE teleop 워치독 상한이다. 호스트 `period_s`는 그 값 이하다
  (20 Hz = 0.05 s ≪ 0.5 s)
- 이 값이 DEVICE에서 워치독 증거를 대신하지 않는다 (D-96)

**Alternatives:** 유실을 0.5 s 참는 안은 마커가 가려진 채 돌게 한다. angular를
정책에만 두는 안은 신경망 플러그인이 한계를 우회한다 (D-99).

**Consequences:** `MatchSetup.angular`가 생긴다. `gate(..., max_linear, max_angular)`.
period > `lost_hold_s`이면 기동하지 않는다.

**Validation / Transition:** `test_gate.py`, `test_cli.py`, `test_heuristic_policy.py`.
DEVICE/FIELD PARKED.

**References:** D-90, D-96, D-99, D-102, SAF-002.

---
