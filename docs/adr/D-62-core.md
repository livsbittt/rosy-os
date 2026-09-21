## D-62 CORE는 필수이고 나머지 런타임은 선택 슬라이스다

**Status:** Accepted (2026-09-16). 설계 결정이며 설치 스크립트·이미지 분리·OMX/AI
실기 인수와 구분한다.

**Context:** Pi 5와 OMX/AI가 같은 미들웨어를 쓰되, 한 이미지에 모터·Nav2·카메라·팔·
추론을 다 넣을 수는 없다. 지금 `core|motor|hardware` 모드는 Nav2와 LiDAR를
hardware에 묶어 두어서 선택 설치가 어렵다. CORE를 프로세스마다 쪼개면 D-1이
깨진다.

**Decision:** `rosy_core` 프로세스와 `rosy-core` 이미지는 필수 슬라이스다. motor,
io, nav, vision, omx, ai는 카탈로그에서 고른다. 각 슬라이스는 localhost ROS
토픽 가족과 프로세스(또는 기존 compose 서비스)를 소유한다. CORE는 슬라이스
패키지를 import하지 않는다. 꺼진 슬라이스의 capability는 false다. 없는
슬라이스를 설치 플래그로 조용히 무시하지 않는다. 사이트 버스와 최종 `cmd_vel`은
바뀌지 않는다.

**Alternatives:** CORE를 메시지 도메인별 노드로 분해하는 안, 단일 이미지+플래그만
쓰는 안을 검토했다. 전자는 단일 프로세스·단일 publisher를 흔들고, 후자는 Pi
이미지에 OMX/NPU를 상시 싣는다.

**Consequences:** `board.yaml` presets가 현재 세 모드와 같게 시작해서 호환을 지킨다.
vision/omx/ai는 카탈로그에만 있고 기본 꺼짐이다. CORE Dockerfile에 이미 있는
OpenCV/`rosy_control`은 부채이며 이 결정이 제거를 강제하지 않는다.

**Validation / Transition:** 카탈로그 시험, CORE import 가드, install preset 해석,
core 스테이지가 omx/imu를 COPY하지 않음을 호스트 시험으로 고정한다.

**References:** [선택 슬라이스 설계](../plans/2026-09-16-optional-runtime-slices-design.md), [실행 계획](../plans/2026-09-16-optional-runtime-slices.md).

---
