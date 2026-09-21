## D-94 rosy_games 천장 OpenCV는 노트북 호스트이며 D-41을 닫지 않는다

**Status:** Accepted (2026-09-18). D-90의 관측 경계다.

**Context:** `rosy_games/host/overhead.py`가 `cv2`를 import한다. D-66은 CORE 이미지에
OpenCV가 없다고 했고, D-41·D-52는 **로봇** ARM64에서 카메라 worker가 어디에 사는지
실측을 요구한다. 노트북 천장 웹캠 코드가 있으면 D-41을 Accepted로 올리려는 혼선이
생긴다.

**Decision:**

- `cv2`는 `rosy_games`의 `host/overhead.py`에만 산다. `field/homography.py`는 순수 기하
- CORE 생산 코드와 CORE 이미지는 OpenCV를 갖지 않는다 (D-66)
- 이 파일은 **관제 노트북 관측 어댑터**다. Pinky 앞 카메라·Picamera2·컨테이너
  배치(D-41, D-52)를 닫지 않는다
- LOCAL pytest는 overhead를 import하지 않고 통과해야 한다. 웹캠 실측은 DEVICE/FIELD

**Alternatives:** overhead를 rosy_control 카메라 worker로 합치는 안은 게임 호스트를
로봇 안에 넣는다 (D-90 위반). D-41을 이 코드로 닫는 안은 Validation 실측을 지운다
(D-91).

**Consequences:** 천장 1v1은 노트북에서만 켠다. 로봇 이미지에 `rosy_games`를 COPY하지
않는다.

**Validation / Transition:** `test/test_rosy_games_surface.py`,
`src/rosy_games/test/test_games_boundaries.py`. ADR 색인 D-41 Status는 Proposed.

**References:** D-41, D-52, D-66, D-90, D-91,
[overhead plan](../plans/2026-09-18-rosy-games-overhead-plan.md).

**Amendment (2026-09-18):** `test/test_overhead.py`는 cv2가 있을 때 `overhead.py`를
import해도 된다. 그건 합성 프레임 LOCAL이다. `test_rosy_games_surface.py`와
`test_games_boundaries.py`는 overhead를 로드하지 않는다. DEVICE는 여전히 실제 웹캠이다
(D-95).

---
