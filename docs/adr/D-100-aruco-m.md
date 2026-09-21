## D-100 골대는 천장에서 ArUco+영역으로 보이고, 득점은 필드 m 폴리곤이다

**Status:** Accepted (2026-09-18). 관측 결정이다. 구현 GO가 아니다.

**Context:** 지금은 골이 `Field.length_m` 양 끝 기하만이다. 천장에서 골대를 못 보면
호모그래피가 틀려도 심판이 같은 좌표로 득점한다. 골 입구를 QR·색 테이프로 보이게
하면 실측이 쉬워진다. 일반 QR은 페이로드용이고, 코너·로봇은 이미
`DICT_4X4_50` ArUco다. 검출기를 두 개 쓰면 천장 한 프레임이 갈라진다.

**Decision:**

- 골 **위치**는 천장 호스트가 본다. CORE·Fleet·`RobotMode`는 골을 모른다
- v1 마커는 코너와 같은 ArUco 사전이다. 일반 QR(QRCodeDetector)은 v1이 아니다
- id **20** = home 골 (negative_x, away가 넣으면 득점). id **21** = away 골
  (positive_x). 로봇 1–2, 코너 10–13과 겹치지 않는다
- 골 **입구**는 선택 HSV 영역(테이프/매트)이다. 마커가 로봇에 가려져도 입구
  폴리곤을 잡을 수 있다
- 피치 축은 여전히 코너 10–13 호모그래피다. 골 마커가 구장을 정의하지 않는다
- 득점은 `game`이 필드 m 폴리곤으로 판정한다 (`in_home_goal` / `in_away_goal`).
  마커·영역은 그 폴리곤을 **갱신**하거나 확인한다. cv2는 `overhead.py`에만 산다
- 양쪽 골 마커가 한 프레임에 없으면 기하 기본값(필드 끝 + `goal_width_m`)으로
  떨어진다. 추측으로 골을 옮기지 않는다
- D-96 계단 1은 코너·로봇·공에 **골 20/21(또는 입구 영역)** 이 보이는지를 포함한다

**Alternatives:** 일반 QR만 쓰는 안은 사전과 검출기를 나눈다. 골 마커만으로
호모그래피를 하는 안은 코너 4점이 사라지면 피치가 흔들린다. 픽셀에서 바로
득점하는 안은 `game`에 cv2를 넣는다 (D-90, D-94).

**Consequences:** `match.yaml`에 `goals.home_id` / `goals.away_id`(기본 20/21)와
선택 `goals.hsv_*`가 추가된다. 구현은 overhead 관측 확장이지 CORE 변경이 아니다.

**Validation / Transition:** 구현 전 색인만. 합성 시험이 생겨도 DEVICE가 아니다
(D-95). 경계: `game/`·`field/`에 cv2 없음.

**References:** D-90, D-94, D-95, D-96.

**Amendment (2026-09-18):** LOCAL 합성 프레임이 골 20/21과 선택 HSV 입구를
필드 m 폴리곤으로 투영한다. 양쪽 마커가 없으면 필드 끝 기하. DEVICE/FIELD는
실제 웹캠 계단 1 전까지 PARKED (D-95, D-96).

---
