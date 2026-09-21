## D-66 CORE 이미지에 rosy_control과 OpenCV가 없다

**Status:** Accepted (2026-09-17). D-63 3단계. 센서 어댑터 소스와 Device ARTIFACT 빌드는 이 결정이 대신하지 않는다.

**Context:** D-64 이후 CORE 생산 코드의 `rosy_control` import는 어댑터 한 파일뿐이다. 그런데 `core` 이미지가 여전히 `python3-opencv`와 `src/rosy_control`을 COPY해서 Pi에 비전 스택을 상시 싣는다. 꺼진 슬라이스가 이미지에 있으면 D-62 카탈로그가 거짓이다.

**Decision:** `rosy-core` 이미지(core-runtime/core-build/core)는 `rosy_control`을 COPY하지 않고 `python3-opencv`를 설치하지 않는다. `rosy_core/package.xml`은 `rosy_control` exec_depend를 두지 않는다. 기본 `control.sensor_adapter.enabled`는 false다. 어댑터를 켠 채 control 슬라이스가 없으면 import가 실패하고 기동은 fail-closed다.

**Alternatives:** 이미지에 패키지를 남기고 capability만 끄는 안(D-62가 버린 안). 어댑터 파일을 토픽 경계로 바꾸는 안은 다음 단계다.

**Consequences:** 기본 CORE는 OpenCV 없이 기동한다. 센서 워커가 필요하면 이후 control/vision 슬라이스 이미지가 패키지를 싣는다. 이 결정이 ARM64 digest를 GO로 만들지 않는다.

**Validation / Transition:** Dockerfile core 스테이지 문자열 가드. `colcon --packages-up-to rosy_core`가 `rosy_control` 소스 없이 성립한다.

**References:** [모듈형 미들웨어 목표](../plans/2026-09-16-modular-middleware-goal-design.md).

---
