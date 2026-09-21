## D-119 스캔·이미지·IMU는 sensor-data QoS다

**Status:** Accepted (2026-09-18). 매칭 계약이다. 측정 함정 2를 ADR로 올린다.

**Context:** 센서 드라이버는 BEST_EFFORT + VOLATILE (`qos_profile_sensor_data`)
인 경우가 많다. 구독이 기본 RELIABLE(depth 10)이면 샘플이 한 줄도 안 온다.
`measure-dds-baseline.sh` 함정 2: `ros2 topic bw` 기본 RELIABLE 는 BEST_EFFORT
퍼블리셔에 0 을 준다. `camera_detect_node` 는 `Image` 를 depth 10(기본
RELIABLE)으로 내고, 구독은 `qos_profile_sensor_data`다. CORE `ros_bridge` 의
scan/imu 구독도 depth 10이다.

**Decision:**

- 생산 코드에서 `LaserScan` / `Imu` / `Image` 의 pub·sub 은
  `qos_profile_sensor_data` 다
- `cmd_vel` 과 latched `map` 은 이 규칙이 아니다 (RELIABLE / TRANSIENT_LOCAL)
- Bool 같은 소형 상태 토픽은 기본 depth 10을 유지해도 된다
- 호스트 시험은 소스 grep 이다. DEVICE GO가 아니다

**Alternatives:** 드라이버를 RELIABLE 로 올리는 안은 센서 파이프가 막히면
cmd_vel 까지 막는다. 구독만 고치고 퍼블리셔를 두는 안은 한쪽만 고친 것이다.

**Consequences:** `camera/front` 퍼블리셔와 CORE scan 구독이 같은 QoS 다.

**Validation / Transition:** `test_dds_rmw_contracts.py`. DEVICE PARKED.

**References:** D-34, D-118.

---
