# DDS 대역폭 감축 — Phase 0 사실 정리

**상태:** 상류 소스로 닫을 수 있는 추론은 닫혔다. 계측 수치는 실물 Pi 대기.
**관련:** ADR D-33(신원), D-34(발행 주기),
`docs/solutions/workflow-issues/inability-to-check-recorded-as-clean-result.md`.
계획 원본은 `.omc/` 아래에 있었고 그 디렉터리는 gitignore 대상이라 이 저장소에
남지 않는다 — 인용하지 않는다.

계획의 §1c는 Nav2 내부 동작에 관한 추론 몇 가지를 "리그에서 확인 필요"로 남겼다.
그중 둘은 하드웨어 없이 상류 소스로 답할 수 있었고, 답하는 과정에서 계획에 없던
사실 하나가 더 나왔다. 그 셋을 여기 적는다 — Nav2는 이 저장소에 vendoring 되어
있지 않으므로, 근거는 인용과 경로로 남긴다.

출처: `ros-navigation/navigation2`, `jazzy` 브랜치.

---

## 1. `publish_frequency`는 `costmap_raw`도 조절한다 — 닫힘

이것이 §1c에서 가장 부담이 큰 추론이었다. Phase 3 이후 브리지가 실제로 구독하는
것은 `_raw` 쌍뿐이므로(`ros_bridge.py`), 만약 `publish_frequency`가 OccupancyGrid
쪽만 조절한다면 D-34의 변경은 대역폭만 줄이고 D2가 지목한 CPU 비용은 그대로
남는다.

`nav2_costmap_2d/src/costmap_2d_ros.cpp`의 `mapUpdateLoop`:

```cpp
if (publish_cycle_ > rclcpp::Duration(0s) && layered_costmap_->isInitialized()) {
  auto current_time = now();
  if ((last_publish_ + publish_cycle_ < current_time) || (current_time < last_publish_)) {
    costmap_publisher_->publishCostmap();
    for (auto & layer_pub : layer_publishers_) { layer_pub->publishCostmap(); }
    last_publish_ = current_time;
  }
}
```

`publish_cycle_`은 `1 / map_publish_frequency_`다. 그리고 그 게이트 안의 단일
`publishCostmap()` 호출이 두 토픽을 함께 낸다 —
`nav2_costmap_2d/src/costmap_2d_publisher.cpp`:

```cpp
if (costmap_pub_->get_subscription_count() > 0 || !costmap_published_once_) {
  prepareGrid();
  costmap_pub_->publish(std::move(grid_));
}
if (costmap_raw_pub_->get_subscription_count() > 0 || !costmap_published_once_) {
  prepareCostmap();
  costmap_raw_pub_->publish(std::move(costmap_raw_));
}
```

**결론:** 같은 호출, 같은 게이트. `publish_frequency: 0.2`는 `costmap_raw`에도
그대로 적용된다. D-34의 효과는 브리지가 실제로 읽는 경로에 도달한다.

## 2. `voxel_grid`는 `update_frequency`에 물려 있다 — 닫힘

`nav2_costmap_2d/plugins/voxel_layer.cpp`의 발행 지점은 `VoxelLayer::updateBounds()`
안이다. `updateBounds()`는 코스트맵의 갱신 주기에서 돌아가므로 `publish_frequency`가
아니라 `update_frequency`(local costmap 기준 5.0 Hz)를 따른다. 발행 주기를 낮추는
것만으로는 이 토픽에 닿지 않았다는 뜻이고, 그래서 별도 항목이어야 했다.

`publish_voxel_map`은 `onInitialize()`에서 퍼블리셔 생성 자체를 가른다:

```cpp
if (publish_voxel_) {
  voxel_pub_ = node->create_publisher<nav2_msgs::msg::VoxelGrid>("voxel_grid", custom_qos);
  voxel_pub_->on_activate();
}
```

**결론:** `False`면 토픽이 아예 존재하지 않는다. 이것은 계측에도 영향을 준다 —
`ros2 topic type <ns>/local_costmap/voxel_grid`가 실패하는 것이 정상 경로다.

## 3. 구독자가 없으면 Nav2는 발행하지 않는다 — 계획에 없던 사실

위 `publishCostmap()` 인용의 `get_subscription_count() > 0` 게이트는 계획이 전혀
다루지 않은 것이고, 두 가지를 바꾼다.

**(a) 계측이 측정 대상을 만든다.** `ros2 topic bw`를 붙이는 행위가 구독자를
만들고, 그러면 Nav2가 `prepareGrid()`를 돌려 발행을 시작한다. 붙이기 전 구독자
수를 함께 기록하지 않으면, 나온 수치가 "원래 흐르던 양"인지 "내가 켠 양"인지
구분할 수 없다. 계획의 §4가 열거한 세 함정에 이것이 빠져 있었다.
`deploy/robot/measure-dds-baseline.sh`가 매 토픽마다 사전 구독자 수를 같이 적고,
0이면 그 행을 표시한다.

**(b) Phase 3의 이득이 기록보다 크다.** 브리지에 있던 두 개의 타입 불일치 구독은
매칭되지 않았으므로 `costmap`(OccupancyGrid) 쪽 구독자 수는 원래 0이었다. 즉
그 토픽은 RViz 같은 외부 구독자가 붙지 않는 한 발행되지 않았고, `prepareGrid()`
비용도 들지 않았다. 반대로 `costmap_raw`는 브리지가 항상 구독하고 있었으므로
계속 나갔다.

**이것은 D-34 본문의 표현 하나를 좁힌다.** "브라우저가 없어도 그대로 나갔다"는
`costmap_raw`에 대해서는 참이다 — 구독자는 브리지이지 브라우저가 아니므로. 다만
`costmap`(OccupancyGrid)에 대해서는 참이 아니었다. ADR 본문은 고치지 않는다(수정이
아니라 대체가 이 저장소의 규칙이고, 결론과 결정은 그대로 유효하다). 정확한 형태는
여기에 남긴다.

---

## 아직 리그가 필요한 것

상류 소스로는 답이 안 나오고 실물 계측이 필요한 항목:

- 토픽별 실제 Hz / KB/s / 평균 크기 — 특히 실제 사이트 맵 크기에서의 절대값.
  계획의 "~160 KB/msg"는 20 m 격자 가정이며 맵에 따라 달라진다.
- 두 컨테이너의 CPU%, idle과 `navigate_to_pose` 주행 중, 그리고 idle 3회 반복에서
  나오는 노이즈 바닥.
- **브라우저 유무 두 조건의 차이.** 이것이 Option D(수요 기반 충전)가 가져갈 몫의
  크기이며, 어느 쪽으로 나오든 기록에 남을 값이다.
- `navigate_to_pose` 회귀: 이전에 성공하던 목표가 여전히 성공하고 경로 길이가
  10% 이내인지.
- 대시보드 맵 오버레이가 15초 이내에 렌더되는지.
- 2대(N=1, N=2)의 `ros2 node list`가 분리되는지 — D-33의 최종 확인.

실행:

```bash
sudo ROSY_RUNTIME_MODE=hardware /opt/rosy/deploy/robot/runtime-mode.sh up
sudo /opt/rosy/deploy/robot/measure-dds-baseline.sh
# 대시보드를 연 채로 한 번, 아무도 열지 않은 채로 한 번
```

스크립트는 `hardware` 모드가 아니면 거절한다. 기본 배포는 core 전용이라 Nav2도
코스트맵 토픽도 없고, 그 상태로 돌리면 "모든 토픽 0 KB/s"라는 그럴듯한 거짓
보고서가 나오기 때문이다.
