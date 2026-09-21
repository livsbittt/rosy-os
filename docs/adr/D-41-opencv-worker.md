## D-41 카메라와 OpenCV worker 실행 위치

**Status:** Proposed (2026-09-12). 설계 결정 상태이며 구현·장치 인수 상태와 구분한다.

**Context:** Picamera2/libcamera의 ARM64 장치 접근과 frame 전달 지연은 실행 위치에 따라 다르다. 현재 HSV 기반 근거는 박스 의미 인식이나 grasp pose가 아니다.

**Decision:** 장치 내부 처리와 CORE/IO 분리는 유지한다. 최소 권한 hardware/vision 컨테이너와 호스트 장치 서비스를 비교한다. 어느 실행 위치도 아직 최종 채택하지 않는다.

**Alternatives:** CORE에 광범위한 장치 권한을 주는 안은 D-22와 충돌한다. 나머지 두 후보는 실제 캡처와 장애 복구 결과로 비교한다.

**Consequences:** G2에서 실행 위치를 먼저 결정해야 관련 그래프와 배포 계약을 고정할 수 있다. 가속기나 OMX 영상 기능은 이번 선택만으로 지원된 것으로 광고하지 않는다.

**Validation / Transition:** T2 초기 G2에서 실제 캡처, 최소 권한, 재시작, frame 시각·손실·p95 지연, CPU·메모리를 측정한다. 장치가 없으면 HOLD. 결과·선택 사유·복구 경로를 남긴 뒤 Accepted로 승격한다.

**References:** [상세 설계](../plans/2026-09-12-rosy-os-control-integrated-design.md), [실행 계획](../plans/2026-09-12-rosy-control-absorption-plan.md), [현재 증거](../plans/2026-09-12-control-absorption-results.md).

---
