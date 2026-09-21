## D-74 작업 명령은 CORE를 거쳐 내부 ROS로 가고 조회는 CORE에 남는다

**Status:** Accepted (2026-09-17). CORE SRS §1.3을 코드 매핑으로 고정한다.

**Context:** 미들웨어의 자리는 하드웨어 ROS와 외부 REST/WS 사이의 유일한 관문이다
(CORE SRS §1.1). 밖은 ROS 토픽을 몰라도 되고, CORE가 작업 요청을 내부 ROS 2
Topic/Action/Service로 바꾼다. 동시에 모든 HTTP가 ROS 명령은 아니다. inventory·
토큰·identity·Host Agent는 CORE에서 끝난다. 이 구분이 ADR에 없으면 새 엔드포인트가
`/cmd_vel`을 직접 열거나, 조회 API를 가짜 ROS 메시지로 감싼다.

**Decision:**

1. 외부 공개 계약은 REST `/api/v1/*`와 WebSocket `/ws/*`뿐이다. concept 05
   `/rosy/{device_id}/…` 토픽 트리는 공개 API가 아니다(D-71).
2. `TaskKind`(MOVE, NAVIGATE, RETURN_HOME, FOLLOW, DOCK)와 e-stop/safety 작업
   명령은 CORE가 중재한 뒤 **내부 ROS**로 나간다. 최종 `cmd_vel` 퍼블리셔는
   CORE뿐이다(D-2, D-38). Fleet은 `cmd_vel`의 원천이 될 수 없다.
3. UART 모터와 도크 HTTP는 ROS 경로 **뒤**의 드라이버이지, 두 번째 공개
   명령 버스가 아니다.
4. `/api/v1/system`, `/api/v1/host`, `/api/v1/logs`, `/api/v1/events`,
   `/api/v1/diagnostics`는 CORE 로컬이다. ROS 메시지로 바꾸지 않는다.

코드 원천은 `rosy_core.domain.command_mapping`이다. 새 `TaskKind`는 여기에
sink를 적기 전에 API에 넣지 않는다.

**Alternatives:** 외부가 Nav2/`cmd_vel`을 직접 쓰는 안은 SRS §1.3과 D-38을
버린다. 모든 REST를 ROS 서비스로 미러하는 안은 조회·토큰까지 DDS에 태운다.
채택하지 않는다.

**Consequences:** 대시보드·Fleet·SDK는 ROSY API만 본다. 브리지는 내부 통역이다.
워크플로 엔진은 여전히 Fleet이다(D-70).

**Validation / Transition:** `src/rosy_core/test/test_command_mapping.py`.
모든 `TaskKind` sink가 `ros`, system/host는 work prefix와 겹치지 않음.
HOST 2026-09-17: `PYTHONPATH=src/rosy_core python -m pytest
src/rosy_core/test/test_command_mapping.py
src/rosy_core/test/test_domain_model.py
src/rosy_core/test/test_capability_descriptors.py
src/rosy_core/test/test_api.py::test_inventory_is_booting_before_diagnostics_arrive
src/rosy_core/test/test_api.py::test_inventory_leaves_booting_after_a_diagnostic
src/rosy_core/test/test_api.py::test_inventory_is_a_mobile_base_without_pick_or_rfid
test/test_module_functional_surface.py -q` → 19 passed.

**References:** CORE SRS §1.3, D-1, D-2, D-12, D-38, D-70, D-71.

---
