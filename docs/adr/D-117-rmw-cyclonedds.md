## D-117 RMW는 CycloneDDS만 쓴다

**Status:** Accepted (2026-09-18). 미들웨어 선택이다. FastDDS 이중 프로파일이 아니다.

**Context:** ROS 2 Jazzy 기본 RMW는 종종 `rmw_fastrtps_cpp`다. Cyclone 노드와
FastDDS 노드는 서로를 조용히 못 본다 — 토픽이 비어 보이면 코드 버그로 읽힌다.
로봇 compose 와 `rosy_env.sh` 는 이미 `rmw_cyclonedds_cpp`다. 개발 `env.sh` 와
`gz_multi` 는 비어 있어, 2026-09-18 WSL 시뮬은 호스트 기본 RMW에 맡겼다.

**Decision:**

- 로봇·개발·시뮬 모두 `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`
- FastDDS/`rmw_fastrtps_cpp` 를 두 번째 프로파일로 두지 않는다
- `env.sh` 가 기본값을 채운다. `gz_multi` 가 런치 환경에 고정한다
- compose·Dockerfile·`rosy_env.sh` 의 Cyclone 지정을 지우지 않는다
- 이 결정이 DDS 실측 GO가 아니다

**Alternatives:** 시뮬만 FastDDS 로 두는 안은 "토픽이 안 보인다"를 재현한다.
Zenoh RMW는 v1 범위 밖이다.

**Consequences:** `test/test_dds_rmw_contracts.py`. ROS-SIM HOLD.

**References:** D-6, D-33, D-114.

**Amendment (2026-09-18):** 빈 RMW를 채우고 잘못된 RMW를 거절하는 기동 훅은 D-121.
웹이 RMW를 바꾸는 API는 없다.

---
