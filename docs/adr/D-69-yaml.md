## D-69 어댑터는 트리 안 YAML 매니페스트다

**Status:** Accepted (2026-09-17). concept 04, 15.

**Context:** concept 04/15는 `rosy-adapter-pinky` apt와 `rosyctl`을 그린다.
살아 있는 어댑터는 `rosy_bringup`(Pinky)과 꺼진 `rosy_omx_adapter`다. D-62는
설치 모듈을 슬라이스로 이미 정했다.

**Decision:** 장치 어댑터는 워크스페이스 패키지 +
`config/adapter.manifest.yaml`이다. CORE `AdapterRegistry`는 YAML만 읽고
OMX/MoveIt 런타임을 import하지 않는다(D-62, D-64). Debian
`rosy-adapter-*`와 `rosyctl`은 만들지 않는다. 매니페스트 `provides`가 비면
(OMX disabled) 능력이 없다. 어댑터는 운용 `cmd_vel`을 발행하지 않는다(D-38).

**Alternatives:** 패키지를 apt 프로파일로 재배치하는 안은 D-62를 뒤집는다.
setuptools entry-point 동적 로딩은 이번 범위가 아니다.

**Consequences:** Pinky/OMX 매니페스트가 카탈로그다. 새 장치는 패키지+YAML로
추가한다. concept 15 Layer 3 apt는 D-71이 미룬다.

**Validation / Transition:** 매니페스트 파싱 시험, CORE가 `rosy_omx_adapter`
코드를 import하지 않는다는 가드.

**References:** [concept 04](../concept/04_ROSY_Device_Adapter_Specification.md), D-57, D-62.

---
