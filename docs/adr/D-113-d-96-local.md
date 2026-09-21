## D-113 D-96 남은 실행은 현장 실측이며 LOCAL 호스트 트랙은 닫힌다

**Status:** Accepted (2026-09-18). 호스트 스위치는 D-107–D-112로 끝이다.

**Context:** 남은 ADR을 호스트에 계속 붙이면 웹캠 없이 계단을 닫는 것처럼
보인다. D-97–D-99·linear 0.20은 계단 4 기록이 전제다.

**Decision:**

- D-96 계단 1–5의 **다음 실행**은 실제 천장 웹캠과 Pinky다
- LOCAL 호스트 계약은 D-107–D-112로 닫는다. 새 호스트 스위치 ADR은 현장
  `logs.md` 실측 항목이 생긴 뒤에만 연다
- DEVICE/FIELD는 PARKED. `--stair`·`ready`·pytest가 GO가 아니다
- 온보드 / `isaac/` / `neural` / 0.20은 여전히 거절 (D-109, D-110)

**Alternatives:** 합성 overhead `ready`로 계단 1을 GO로 적는 안은 D-95다.
호스트 ADR을 더 만들어 현장을 미루는 안은 이 결정이 거절한다.

**Consequences:** 다음 세션 명령은 `--stair 1 --observer overhead --preview`.

**Validation / Transition:** `progress.md` FIELD PARKED. `test_rosy_games_surface.py`.

**References:** D-91, D-95, D-96, D-107, D-108, D-109, D-110, D-111, D-112.

---
