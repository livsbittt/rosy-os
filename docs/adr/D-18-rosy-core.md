## D-18 프로토콜 스키마 재사용 — rosy_core 단일 소스 유지

**Status:** Accepted (2026-08-29)

**Context:** P1-19에서 `rosy_core/protocol/schemas.py`(envelope·이벤트·ack)를 고정했다. Phase 4의 rosy_fleet도 동일 스키마가 필요하다. 독립 공유 패키지(예: rosy_protocol) 분리도 선택지였다.

**Decision:** 별도 패키지 분리는 보류하고, rosy_fleet이 `rosy_core`(ament_python 의존)를 import하여 재사용한다. 스키마 변경 시나리오는 양측이 같은 리포 내에서 동시 컴파일되므로 계약 파열이 구조적으로 차단된다.

**Consequences:** 초기 복잡도 최소화, 중복 제거. 단 rosy_fleet Docker 이미지에 rosy_core가 포함되는 부피와, 로봇 패키지 의존이 fleet 서버에 끼치는 영향은 P4 패키징 시 재검토(3번째 소비자 등장 시 분리 재고).

---
