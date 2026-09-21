## D-114 gz_multi 시뮬은 도메인 하나·네임스페이스·ros_gz_bridge다

**Status:** Accepted (2026-09-18). 시뮬 통신 모델이다. ROS-SIM GO가 아니다.

**Context:** 실기는 `ROS_DOMAIN_ID = 40+N` 과 localhost CycloneDDS 로 로봇 간 DDS를
끊고, 관제는 CORE REST 다 (D-33, D-81). `gz_multi` 는 Gazebo 하나 위에 N대를
띄우므로 도메인을 나누면 spawn·clock·`/tf` 가 깨진다. ROS 2 `domain_bridge` 와
`rosy_env.sh` 를 시뮬에 얹으면 실기 격리를 흉내 내는 것처럼 보이지만, 관제가 쓰는
경로는 HTTP 라 그 브리지는 관제를 닫지 않는다.

2026-09-18 WSL 실측: `parameter_bridge` 두 개가 `rosy_01`/`rosy_02` 의
scan/cmd_vel/odom 을 이었고 `domain_bridge` 프로세스는 없었다. 관제
`127.0.0.1:8090` 은 8080/8081 REST 로 2/2 online 이었다.

**Decision:**

- `gz_multi` 는 **도메인 하나** + `rosy_XX` 네임스페이스다
- Gazebo↔ROS 는 **`ros_gz_bridge` `parameter_bridge`** 다. 로봇마다 YAML 을 만든다
- ROS 2 `domain_bridge` 를 `gz_multi` 에 넣지 않는다
- `rosy_env.sh` / 로봇별 `ROS_DOMAIN_ID` 를 `gz_multi` 에 source 하지 않는다
- 시뮬 관제는 계속 CORE REST (D-81). 관제 UI 가 DDS/`cmd_vel` 에 붙지 않는다
- 이 결정이 ROS-SIM GO 가 아니다 (D-79, D-83, D-87)

**Alternatives:** 시뮬에도 로봇별 도메인을 쓰는 안은 한 Gazebo 월드의 clock/TF 를
나눈다. `domain_bridge` 로 관제 PC 를 도메인 0 에 두는 안은 관제가 이미 HTTP 라
중복이다.

**Consequences:** 실기 D-33 과 시뮬 네임스페이스는 다른 모델이다. 시뮬 DDS
디스커버리 흔들림을 실기 격리가 안 된 증거로 쓰지 않는다.

**Validation / Transition:** `test_gz_package_contract.py`. ROS-SIM HOLD.

**References:** D-6, D-33, D-79, D-81, D-83, D-87.

---
