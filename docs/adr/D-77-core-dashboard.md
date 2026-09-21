## D-77 운용자 콘솔은 CORE `/dashboard` 하나다

**Status:** Accepted (2026-09-17). D-72 S8. concept 16 §2.

**Context:** D-72가 남긴 질문이다. 운용자가 "이 로봇 괜찮나"에 답이 둘이다 —
`rosy_core` FastAPI `/dashboard`와 `rosy_control` `web_node`가 서빙하는
`dashboard.html`. 선택지는 셋이었다. (a) CSP nonce로 control 단일 파일을
자족 콘솔로 유지. (b) `dashboard.html`을 분해해 CORE 자산에 편입.
(c) 서버 둘을 유지. (a)와 (b)는 ROS-SIM·DEVICE 게이트와 두 맵 파이프라인
(S2), 그리고 `web_node`의 `/cmd_vel_raw` 발행(D-38)을 건드린다.

운용 compose(`deploy/robot/compose.yaml`)는 이미 `rosy_control/launch`를
띄우지 않는다. device-validation 계획 §1은 `robot.launch.py`를 CORE와 함께
돌리지 말라고 적는다. 그런데 문서와 control 페이지 제목은 둘을 같은 콘솔로
부르고 있었다.

**Decision:** v1 운용자 콘솔은 **CORE `/dashboard` 하나**다 (D-23, D-75).

- (c)를 고르되, 두 *운용자* 콘솔이 아니라 역할이 다른 두 HTTP 표면이다.
- `rosy_control` `web_node`+`dashboard.html`은 흡수된 IO 스택의 진단 화면이다.
  레거시 `robot.launch.py`에서만 뜬다. CORE와 같이 올리지 않는다.
- (a)는 기각한다. 두 번째 운용자 콘솔을 자족적으로 만들면 같은 질문에 답이
  둘로 남는다.
- (b)는 DEVICE 전까지 미룬다. CORE `map.js`와 control `/map.png`는 별개
  파이프라인이고, `web_node` teleop은 `cmd_vel_raw`를 낸다. 합치면 D-38과
  S2 경계를 한 번에 연다.

**Alternatives:** (a)는 답이 둘인 문제를 남긴다. (b)를 지금 하는 안은
맵 파이프라인과 명령 경로를 DEVICE 증거 없이 합친다. 둘 다 채택하지 않는다.

**Consequences:** "이 로봇 괜찮나"의 운용자 답은 `/dashboard`다. control
진단 화면은 레거시 런치에 남고, 교차 패키지 토큰 시험은 여전히 D-73 거처가
없다(concept 16 §6). 이 결정이 DEVICE/ARTIFACT GO가 아니다.

**Validation / Transition:** `test/test_control_launch_boundary.py` —
compose에 `web_node`/`dashboard.html`/`rosy_control/launch`가 없다.
concept 16 §2 표면 표. HOST 시험이지 Device viewport가 아니다.

**References:** D-23, D-38, D-72, D-73, D-75,
[concept 16](../concept/16_ROSY_Interface_Design_Principles.md),
[device-validation](../plans/2026-09-13-rosy-os-device-validation-implementation-plan.md).

---
