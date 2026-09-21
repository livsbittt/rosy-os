## D-64 CORE 생산 코드의 rosy_control import는 센서 어댑터뿐이다

**Status:** Accepted (2026-09-16). 설계 결정이며 이미지 COPY 축출과 구분한다.

**Context:** `safety/manager.py`가 `rosy_control.control.command_gate`와
`actuation`을 import한다. 흡수 어댑터 밖에서도 Control 타입을 알고 있으면
안전 패키지가 센서 스택에 묶인다. D-63 2단계.

**Decision:** `src/rosy_core/rosy_core/` 아래 `rosy_control` import는
`bridge/control_sensor_adapter.py`만 허용한다. SafetyManager의
`bind_control_policy` / `bind_simulation_actuation`은 타입 모듈을 import하지
않고 evaluate/revision 등 공개 속성으로 duck-type 한다. 시험 파일의
rosy_control import는 허용한다. CORE 이미지에서 rosy_control을 빼는 일은
후속이다.

**Alternatives:** SafetyManager에 CommandPolicy를 남기는 안은 경계를 문서만으로
둔다. rosy_control 전체를 이번 단계에서 이미지에서 빼는 안은 센서 어댑터
런타임을 한꺼번에 옮긴다. 채택하지 않는다.

**Validation / Transition:** AST 가드 시험이 어댑터 외 import를 실패시킨다.
기존 control policy 링크 시험은 통과해야 한다.

**References:** [실행 계획](../plans/2026-09-16-core-control-import-boundary.md).

---
