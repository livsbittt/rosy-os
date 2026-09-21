## D-97 온보드 축구 시야는 FIELD 반복 뒤 CMD-001 후보다

**Status:** Accepted (2026-09-18). 아직 구현하지 않는다.

**Context:** Pinky 앞 카메라는 320×240, 8 fps, 바닥 전방용이다. 지금 온보드 blob을
넣으면 시야 밖 공을 잃고, D-41 로봇 카메라 위치를 게임으로 닫게 된다.

**Decision:**

- D-96 계단 4가 여러 번 반복되기 전에 온보드 공 추적을 열지 않는다
- 열릴 때도 최종 `cmd_vel`은 CORE다. 온보드는 CMD-001 속도 후보이거나 호스트가
  쓰는 로컬 관측이다
- 심판(득점, 킥오프, 양쪽 stop)은 노트북 `rosy_games`에 남는다
- 이 코드는 D-41·D-52를 Accepted로 올리지 않는다

**Alternatives:** 앞 카메라만으로 1v1을 시작하는 안은 천장 호스트를 버린다.
온보드가 `cmd_vel`을 내는 안은 D-2·D-38 위반이다.

**Consequences:** 1단계 실기는 천장 카메라다. 온보드 패키지/슬라이스는 별도 계획.

**Validation / Transition:** `isaac/`과 온보드 플레이어 패키지가 트리에 없다.
구현은 D-96 계단 4 기록 다음 문서.

**References:** D-2, D-38, D-41, D-90, D-94, D-96.

**Amendment (2026-09-18):** 호스트 observer 카탈로그 잠금은 D-109. `--onboard`를
지금 만들지 않는다. D-41 Status는 Proposed로 남는다.

---
