## D-76 501 본문의 capability는 CAP-001이고 concept_id는 부가다

**Status:** Accepted (2026-09-17). D-68 잔여. 에러 코드와 CAP-001 feature 필드는 유지한다.

**Context:** TaskKind는 개념 id(mobility.move)를 알고, 501은 CAP-001 플래그(	eleop)만 말한다. 클라이언트가 inventory descriptors와 에러 본문을 맞추려면 concept_id가 필요하지만, feature를 바꾸면 CAP-003 계약이 깨진다.

**Decision:** CapabilityError.feature는 CAP-001 dotted flag로 남고 501 detail.capability도 그대로다. TaskKind.require()가 실패하면 detail.concept_id를 부가한다. slam 등 TaskKind가 아닌 require()는 concept_id를 넣지 않는다. SAFE_STOP에서 거절은 계속 safety/e-stop이지 501이 아니다.

**Alternatives:** feature를 개념 id로 교체하는 안은 기존 501 소비자를 깨뜨린다. 채택하지 않는다.

**Consequences:** 조회는 inventory descriptors, 게이트는 CAP-001, 에러는 둘 다 담는다.

**Validation / Transition:** 	est_taskkind_require_keeps_cap001_flag_and_adds_concept_id, 	est_disabled_navigation_capabilities_return_501의 concept_id 단언.

**References:** D-11, D-32, D-68, D-74.

---
