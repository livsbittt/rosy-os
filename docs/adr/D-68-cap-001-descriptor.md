## D-68 CAP-001과 개념 descriptor는 문서를 나눈다

**Status:** Accepted (2026-09-17). concept 07. `0728125`.

**Context:** D-11은 `GET /api/v1/system/capabilities`에 CAP-001 YAML 불리언을
둔다. concept 07은 `mobility.move` 같은 id와 동적 가용성을 원한다. 한
문서에 둘을 섞으면 CAP-001 소비자가 깨진다(D-32).

**Decision:** CAP-001 본문은 바꾸지 않는다. 개념 id는 inventory
`descriptors[]`(`id`, `available`)와 `capability_ids`에만 둔다. YAML이 true인
플래그만 광고한다. `manipulate.pick` / `scan_rfid` / `infer` / `train`은
슬라이스가 생기기 전에 광고하지 않는다. `available`은 DeviceState가
BOOTING·FAULT·SAFE_STOP·OFFLINE·UPDATING이면 false다. `TaskKind.require()`는
CAP-001 플래그로 501을 유지한다.

**Alternatives:** CAP-001을 개념 id로 교체하는 안, 정적 YAML만 두고 가용성을
숨기는 안. 전자는 D-11 소비자를 깨고, 후자는 concept 07 §5를 무시한다.

**Consequences:** Fleet/SDK는 기존 capabilities를 읽고, 개념 뷰는 inventory를
읽는다. require()가 concept id를 말하게 바꾸는 것은 에러 본문 계약이므로
별도 ADR이 필요하다.

**Validation / Transition:** `test_capability_descriptors.py`,
`test_inventory_is_a_mobile_base_without_pick_or_rfid`. HOST 2026-09-17:
SAFE_STOP/BOOTING에서 `available=false`, pick/rfid/infer/train 없음.

**References:** [concept 07](../concept/07_ROSY_Capability_Model.md), D-11, D-32.

---
