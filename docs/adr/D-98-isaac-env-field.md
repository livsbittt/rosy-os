## D-98 Isaac 축구 env는 FIELD 반복 전 폴더를 만들지 않는다

**Status:** Accepted (2026-09-18). 아직 구현하지 않는다.

**Context:** Isaac은 학습장으로 예약됐다. 빈 `isaac/` 패키지는 학습이 있는 것처럼
보인다. Gazebo(`rosy_gz_sim`)는 CORE ROS-SIM용이다.

**Decision:**

- `src/rosy_games/rosy_games/isaac/`은 D-96 계단 4가 반복되기 전에 만들지 않는다
- 열릴 때 Lab env는 `game.reset` / `game.step`만 호출한다. 규칙을 Isaac 스크립트에
  복제하지 않는다
- `rosy_gz_sim`을 축구 체육관으로 승격하지 않는다
- Isaac이 실기 Command Manager를 대체하지 않는다

**Alternatives:** 지금 빈 폴더를 두는 안은 이미 지웠다. Isaac이 경기를 소유하는 안은
D-90이 거절했다.

**Consequences:** Isaac 없는 실기 1v1이 `game`만으로 성립해야 한다.

**Validation / Transition:** 트리에 `rosy_games/isaac/`이 없다.

**References:** D-83, D-90, D-96, D-99.

**Amendment (2026-09-18):** 카탈로그 거절은 D-109. 빈 `isaac/`을 다시 만들지 않는다.

---
