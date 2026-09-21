## D-63 모듈형 미들웨어 목표 — CORE는 얇고 슬라이스는 선택이다

**Status:** Accepted (2026-09-16). 목적지 결정이다. 구현은 자식 ADR이 한 이음새씩 닫는다.

**Context:** Pi 5와 OMX/AI가 같은 미들웨어를 써야 한다. CORE에 카메라·팔·추론·Nav2가
섞이면 설치와 책임이 다시 한 덩어리가 된다. D-62는 카탈로그만 열었다.

**Decision:** 끝 상태는 이것이다. CORE 프로세스와 `rosy-core` 이미지는 필수이고 얇다
(API, 안전, 최종 `cmd_vel`, 사건, 대시보드). motor/io/nav/vision/omx/ai는 선택
슬라이스이며 각자 ROS 메시지 가족과 프로세스를 소유한다. CORE는 슬라이스
패키지를 import하지 않는다. 이미지는 고르지 않은 스택을 싣지 않는다. CORE
프로세스를 쪼개지 않고, 로봇에 사이트 브로커를 올리지 않는다.

**Sequence:** D-62 카탈로그 → D-64 CORE의 rosy_control import 경계 → 이후 이미지
축출, 매핑 분리, nav overlay, vision/omx 설치 가능 overlay.

**Consequences:** 이 ADR만으로 이미지를 바꾸거나 하드웨어를 켜지 않는다. 자식 ADR이
없을 때 “모듈화 완료”라고 말하지 않는다.

**References:** [목표 설계](../plans/2026-09-16-modular-middleware-goal-design.md).

---
