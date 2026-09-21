## D-22 Raspberry Pi OS 런타임: Core/I/O 컨테이너 분리 + 드라이버 deadman

**Status:** Superseded by D-161 (2026-09-21). CORE/I/O 분리와 driver deadman의
안전 의도는 유지한다.

**Context:** 제품의 1차 장치는 Raspberry Pi 5 8GB와 Raspberry Pi OS Lite
64-bit다. ROS 2 Jazzy의 기존 네이티브 배포안은 Ubuntu 24.04를 전제로
하고 있으며, 현재 `rosy_core`는 장치를 직접 열지 않고 `rosy_bringup` 등
Driver Adapter를 통해 명령한다. 단일 컨테이너는 FastAPI와 모든 장치
권한을 결합하고, 한 노드의 장애가 전체 런타임 재시작으로 확대된다.

**Decision:** Ubuntu Noble 기반 ROS 2 Jazzy 사용자 공간을 OCI 이미지로
제공한다. 런타임은 장치 권한이 없는 `rosy-core`와 Pinky Pro 장치
어댑터를 실행하는 `rosy-io`로 나눈다. 두 서비스는 동일한 host network,
`ROS_DOMAIN_ID`, localhost CycloneDDS 정책으로 통신한다. `rosy-io`에는
열거된 장치만 전달하며 `privileged` 모드는 금지한다. 모터 어댑터는 마지막
정상 `cmd_vel` 이후 설정된 시간(기본 500 ms)이 지나면 독립적으로 zero RPM을
명령한다.

**Consequences:** Raspberry Pi OS 호스트에 ROS 2를 별도로 포팅하지 않고
Jazzy 사용자 공간을 고정할 수 있으며, 외부 API와 장치 권한이 분리된다.
반면 host networking, 장치 UID/GID, 이미지 빌드·승격, 두 서비스의 장애
복구를 운영해야 한다. 소프트웨어 deadman은 안전 인증 수단이 아니며,
고위험 용도에는 하드웨어 E-stop 또는 독립 컨트롤러가 추가로 필요하다.

---
