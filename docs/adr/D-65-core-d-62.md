## D-65 개념 객체는 CORE와 D-62 슬라이스에 매핑한다

**Status:** Accepted (2026-09-17). inventory API, 어댑터 매니페스트, Phase 3
descriptor availability가 올라왔다.

**Context:** `docs/concept`는 분산 OS 목표(Node/Device/Component/Capability/
Asset/Task, apt 프로파일, 제어면)를 적는다. 살아 있는 스택은 Pinky CORE와
Docker이며, "필요한 것만 설치"는 D-62 슬라이스가 이미 결정했다. D-61–D-64는
기록·슬라이스 카탈로그·미들웨어 목표·import 경계다. 목표 문서를 코드처럼
읽거나 목표 용어를 무시하면 이후 작업이 두 어휘를 만든다.

**Decision:** v1은 concept 객체를 CORE + D-62 슬라이스에 매핑한다. 호스트는
Node(`RuntimeNode`), CORE가 관리하는 로봇은 Device(`device_id` = robot id),
구동·LiDAR 등은 Component, YAML 플래그는 Capability, 단위는 단일 Device
Asset, REST 원자 액션은 Task(`TaskKind`)다. Concept 15 apt/`rosyctl`과 제어면은
concept 13의 이후 단계다. Concept 05 ROS 토픽(`/rosy/{device_id}/state`)은
외부 API가 아니다(CORE SRS §1.3).

**Alternatives:** 저장소를 Debian `rosy-profile-*`와 `rosyctl`로 전면 재작성하는
안, 용어만 고치고 매핑을 남기지 않는 안을 검토했다. 전자는 D-1·D-38·D-62를
버리고, 후자는 목표 문서와 런타임이 계속 어긋난다. 채택하지 않는다.

**Consequences:** `CONCEPTS.md`가 살아 있는 용어집이다. concept 본문 00–15는
목표로 남고 이 결정이 재작성하지 않는다. 복합 Pinky+OMX Asset, compute/AI,
워크플로 엔진은 v1이 아니다(D-12). D-63 모듈형 미들웨어 목표와 D-64 import
경계는 그대로다.

**Validation / Transition:** `CONCEPTS.md` 여섯 객체, `GET /api/v1/system/inventory`,
Pinky/OMX 매니페스트, `TaskKind.concept_id`와 inventory `descriptors`.

**References:** [concept-runtime-alignment 설계](../plans/2026-09-16-concept-runtime-alignment-design.md), [concept 13 이관](../concept/13_ROSY_Current_to_Target_Migration.md).

---
