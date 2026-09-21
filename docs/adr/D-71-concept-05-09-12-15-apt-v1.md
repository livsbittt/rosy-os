## D-71 concept 05·09–12·15 apt는 v1 미들웨어가 아니다

**Status:** Accepted (2026-09-17). 목표 OS 나중 단계의 명시적 연기.

**Context:** concept 폴더는 분산 제어면, `/rosy/{device_id}/state` 토픽 트리,
Pinky+OMX 합성 Asset, Gram/RTX 패브릭, VLA, Teach-Record-Train, apt/`rosyctl`,
concept 14의 Gram/합성 수락을 그린다. 이를 현재 스프린트 백로그로 읽으면
D-1·D-12·D-38·D-62와 충돌한다.

**Decision:** 다음을 v1 미들웨어가 아니라고 고정한다.

- concept 05 공개 토픽/액션 트리. 외부 클라이언트는 REST/WS만 쓴다.
- concept 09 합성 Asset. D-55가 OMX를 켜기 전에는 `asset.type=mobile_base`
  단일 Device다.
- concept 10 Compute Fabric (Gram/RTX 역할 노드).
- concept 11 모델 레지스트리·VLA·정책 배포. vision/ai는 D-62 카탈로그만.
- concept 12 데이터셋/에피소드 파이프라인.
- concept 15 `rosy-runtime-*` apt 메타패키지와 `rosyctl`.
- concept 14의 Gram 인식·합성 태스크 수락. Device GO는 Device 검증 계획이
  정한다.

**Alternatives:** concept 본문을 v1 범위로 다시 쓰는 안은 목표 문서를 지운다.
지금 패브릭을 구현하는 안은 CORE를 제어면으로 만든다. 채택하지 않는다.

**Consequences:** 미들웨어 작업은 D-67–D-70과 Device ARTIFACT 계획 안에서
한다. 09–12 구현 PR은 이 ADR을 먼저 뒤집어야 한다.

**Validation / Transition:** concept README 매핑 표의 target-not-built 행.
합성·패브릭·rosyctl 코드가 `rosy_core`에 생기면 실패로 본다.

**References:** [concept README](../concept/README.md),
[concept 폴더 ADR 계획](../plans/2026-09-17-concept-folder-adr-plan.md).

---
