## D-101 축구 호스트 화면은 노트북 게임 표면이며 CORE `/dashboard`가 아니다

**Status:** Accepted (2026-09-18). 표면 분할이다. DEVICE/FIELD GO가 아니다.

**Context:** D-96 계단 1은 천장에서 구장·공·로봇·골 20/21이 **보이는지**다.
지금은 CLI와 합성 pytest만 있다. 그 미리보기를 CORE `/dashboard`에 붙이면
운용자 콘솔이 경기를 삼킨다(D-77). `rosy_control` `dashboard.html`에 붙이면
진단 화면이 게임이 된다. CORE CSS를 import하면 L2를 파일로 공유하는 결함이다
(D-92). 번들러를 들이면 D-75를 게임으로 우회한다.

**Decision:**

- 축구 미리보기는 **노트북 게임 표면**이다. 질문: "구장·공·로봇·골이 보이는가"
- CORE `/dashboard`에 경기 보드·천장 JPEG·골 칩을 넣지 않는다
- `rosy_control/web/dashboard.html`에 경기를 넣지 않는다
- 자산은 `rosy_games/web/` 손수 정적 HTML·CSS·ES 모듈이다. 번들러·npm·CDN 없음
- 노트북 `127.0.0.1`만 연다. `rosy_games match --preview`. 기본은 끔 (D-95와 같이
  실기 실수와 pytest를 갈라 둔다)
- 미리보기 서버는 stdlib `http.server`다. cv2는 `overhead.py`에만 산다.
  `host/preview.py`와 `host/loop.py`는 cv2를 import하지 않는다
- 보드가 그리는 것은 필드 m 오버레이(관측 JSON)다. JPEG는 overhead가 준
  바이트를 그대로 붙일 뿐이며, 픽셀에서 득점하지 않는다 (D-100)
- 표면 사이에 CSS·컴포넌트를 import하지 않는다. 게임 L2는 피치·점수·마커 칩이다
- 이 페이지는 teleop·`cmd_vel`·CORE FastAPI를 열지 않는다. 정지는 기존 호스트
  `safety/stop`이다
- 합성 보드 ≠ DEVICE (D-95). D-96 계단 1은 실제 웹캠 기록이다

**Alternatives:** CORE 운용/점검 탭에 축구를 넣는 안은 D-77을 깨뜨린다. 공용
`components.css`를 가져오는 안은 D-92다. `cv2.imshow`만 쓰는 안은 호스트
문법이 없고 시험이 화면을 못 잠근다.

**Consequences:** concept 16 §2에 Game host 행이 생긴다. CORE 이미지·슬라이스·
`dashboard_assets` allowlist에 게임 보드가 없다. D-96 계단 1의 노트북 도구다.

**Validation / Transition:** `test/test_rosy_games_surface.py`,
`src/rosy_games/test/test_preview.py`, `test_games_boundaries.py`.
DEVICE/FIELD PARKED.

**References:** D-23, D-72, D-75, D-77, D-90, D-92, D-94, D-95, D-96, D-100,
[concept 16](../concept/16_ROSY_Interface_Design_Principles.md).

---
