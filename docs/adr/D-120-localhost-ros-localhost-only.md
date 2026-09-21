## D-120 시뮬 디스커버리는 LOCALHOST 범위이며 ROS_LOCALHOST_ONLY를 쓰지 않는다

**Status:** Accepted (2026-09-18). Jazzy 디스커버리 계약이다. D-6 localhost
프로파일을 대체하지 않는다.

**Context:** Jazzy 는 `ROS_LOCALHOST_ONLY` 를 deprecated 로 두고
`ROS_AUTOMATIC_DISCOVERY_RANGE` 를 쓴다. 2026-09-18 `gz_multi` 로그가 그
경고를 냈다. 로봇 격리는 Cyclone `NetworkInterface name="lo"` 이지 이 env 가
아니다 (D-6, D-33, `RosGraphMonitor`). 시뮬은 도메인 하나·한 기계라 범위
LOCALHOST 면 충분하다 (D-114).

**Decision:**

- `gz_multi` 와 개발 `env.sh` 는 `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`
- `ROS_LOCALHOST_ONLY` 를 새로 켜지 않는다
- 로봇 compose/`rosy_env.sh` 는 Cyclone lo XML 을 유지한다. 시뮬에
  `rosy_env.sh` 를 source 하지 않는다 (D-114)
- 이 env 가 WiFi 실측 GO가 아니다

**Alternatives:** 시뮬에도 Cyclone lo XML 만 쓰는 안은 share 경로가 없는
부분 오버레이에서 실패한다. `SYSTEM` 범위는 같은 LAN 의 다른 ROS 그래프와
섞인다.

**Consequences:** 호스트 기본 FastDDS + 멀티캐스트 디스커버리를 시뮬이 물려받지
않는다 (D-117과 함께).

**Validation / Transition:** `test_gz_package_contract.py`, `env.sh`.

**References:** D-6, D-33, D-114, D-117.

---
