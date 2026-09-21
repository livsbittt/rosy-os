## D-118 생 Image는 Fleet·보드·gz_multi 브리지에 타지 않는다

**Status:** Accepted (2026-09-18). 전송 경로 계약이다. D-41을 닫지 않는다.

**Context:** `sensor_msgs/Image` 한 장은 스캔보다 수십 배 크다. DDS 로 사이트
WiFi·관제 PC·브라우저까지 실으면 cmd_vel/scan 이 밀린다. 흔한 ROS 함정이다.
CORE 대시보드와 게임 보드는 JPEG/HTTP 다 (D-75, D-101). `gz_multi` 의
`parameter_bridge` 는 이미지를 안 싣는다. 옛 `launch_sim.launch.xml` 은
`ros_gz_image` 를 `/camera/image_raw` 와 `/camera` 에 **두 번** 붙인다.

로봇 안 `camera/front` 는 온보드 검출용으로 남는다. 그걸 Fleet envelope 이나
노트북 천장 호스트로 미는 것이 금지다.

**Decision:**

- `gz_multi` `BRIDGE_TEMPLATE` 과 `rosy_bridge.yaml` 에 `sensor_msgs/msg/Image` 가
  없다
- `gz_multi` 는 `ros_gz_image` / `image_bridge` 를 띄우지 않는다
- `launch_sim.launch.xml` 의 image_bridge 는 `bridge_image:=true` 일 때만, 토픽
  하나 (`/camera/image_raw`)
- Fleet 과 `rosy_games` 는 `sensor_msgs` Image 를 import 하지 않는다
- 운용 화면은 JPEG/HTTP. 생 Image 를 브라우저에 싣지 않는다
- D-41 ARM64 카메라 배치는 이 ADR 이 닫지 않는다

**Alternatives:** compressed Image 토픽을 사이트 DDS 로 여는 안은 여전히
cmd_vel 과 큐를 다툰다. 천장 웹캠을 CORE 대시보드에 넣는 안은 D-101 이다.

**Consequences:** 온보드 `camera/front` 는 로봇 프로세스 안에 남는다.

**Validation / Transition:** `test_gz_package_contract.py`, `test_dds_rmw_contracts.py`.

**References:** D-34, D-41, D-75, D-94, D-101, D-114.

---
