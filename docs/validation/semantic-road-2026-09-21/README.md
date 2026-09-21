# Semantic road control validation (2026-09-21)

## Actual Gazebo runtime result

`GAZEBO_CAMERA_GRAPH_PASS` / `GAZEBO_METRIC_STOP_DISTANCE_PASS`

WSL2 Ubuntu 24.04.4, ROS 2 Jazzy, Gazebo Harmonic에서 실제
`semantic_road_dashboard.launch.py gazebo_gui:=false`를 실행했다. Gazebo가
설치 overlay의 `map_260905_traffic.world`를 로드했고 소스와 설치본의
SHA-256은 `af70bbd...a87373`으로 일치했다.

실제 `/camera/front` 프레임은 `GAZEBO`, `front_camera_link`, 320x180으로
수신됐다. production road detector는 정지선을 confidence `0.812804`, image
row `107.5`에서 검출했다. Gazebo URDF에 선언된 카메라 높이·pitch·FOV로만
구성되는 simulation-only pinhole 모델이 거리 `0.108313 m`를 계산했다.
물리 카메라 homography와 사용자가 제공한
`approximate_requires_physical_validation` 값은 활성화하지 않았다.

CORE에서 `CAMERA_LINE`을 선택한 뒤 traffic policy는 기존의
`stop_distance_unavailable`에서 벗어나 `WAIT_SIGNAL / signal_unknown`을
보고했다. 현재 시야에는 신호등이 보이지 않으므로 진행을 허용하지 않았고,
실제 readback 속도는 linear `0.0 m/s`, angular `0.0 rad/s`였다.

![Actual Gazebo front camera frame](gazebo_camera_frame.jpg)

이 WSL software-rendering 환경에서 320x180 raw ROS camera는 약
`2.026~2.651 Hz`, dashboard preview는 `1.323~1.501 Hz`였다. CORE preview
status는 `stale=false`, capture age `229 ms`였다. 640x360 진단에서는 raw ROS
전달이 약 1.9 Hz였고, 320x180에서 2 Hz 이상으로 회복되어 raw RGB bridge/DDS
복사량이 이 호스트의 주 병목임을 확인했다. semantic launch는
`camera_width`, `camera_height`, `camera_update_rate`를 공개하므로 호스트 성능에
맞춰 조정할 수 있다.

## Deterministic host simulation result

`SEMANTIC_ROAD_HOST_SIM_PASS`

The `map_260905_update_v2` geometry is preserved and a derived semantic road
scene adds one lane, one stop line, one crosswalk, and one traffic signal. The
host simulation exercises the production detector, strict bridge decoder,
line-follow manager, traffic policy, and the atomic command gate immediately
before the sole CORE Command Manager.

| Phase | Detected / policy state | Final linear command |
|---|---|---:|
| clear | lane / `FOLLOW` | 0.07984 m/s |
| approach | stop line + red / `APPROACH` | 0.04139 m/s |
| red stop | crosswalk + stop line + red / `STOP_REQUIRED` | 0.00000 m/s |
| red wait | crosswalk + stop line + red / `WAIT_SIGNAL` | 0.00000 m/s |
| green proceed | crosswalk + stop line + green / `PROCEED` | 0.02457 m/s |
| stale | expired observation / `HOLD` | 0.00000 m/s |

Semantic YAML truth is used only to build and audit the scene. It is not fed
to the detector. `result.json` records
`semantic_truth_fed_to_detector: false` and
`physical_device_validated: false`.

## Evidence

- `gazebo_runtime_result.json`: actual Gazebo camera, detector, metric range,
  and CORE readback.
- `gazebo_camera_frame.jpg`: actual Gazebo frame pulled from CORE's authenticated
  preview endpoint; this is not a HOST-SIM fixture.
- `result.json`: deterministic policy and command samples.
- `semantic_road_simulation.svg`: state/command timeline.
- `camera_detection_montage.png`: synthetic camera inputs used by the production
  detector.
- `camera_live_dashboard.png`: prior HOST-SIM browser fixture, not evidence of
  the live Gazebo process.
- `traffic_policy_dashboard.png`: prior browser evidence of policy controls.
- `src/apps/control/map/map_260905_update_v2/review/map_260905_traffic.png`:
  semantic overlay on the measured 16-wall map.
- `src/apps/control/map/map_260905_update_v2/worlds/map_260905_traffic.world`:
  Gazebo world with lane, crosswalk, stop line, and signal models.

The in-app browser inventory was empty during this run, so a live full-dashboard
screenshot was not captured. The authenticated API frame above and API state
readback are actual runtime evidence; the browser screenshot gate remains
`HOLD_NO_BROWSER_BACKEND` rather than being substituted with a fixture.

## Reproduce

```bash
source /opt/ros/jazzy/setup.bash
source <workspace>/install/setup.bash
ros2 launch gz_sim semantic_road_dashboard.launch.py gazebo_gui:=false
```

Tune only when the host requires it:

```bash
ros2 launch gz_sim semantic_road_dashboard.launch.py \
  camera_width:=640 camera_height:=360 camera_update_rate:=5
```

Then open `http://127.0.0.1:8080/dashboard`, enter the Viewer token, and check
that the camera source reads `GAZEBO`.

## Acceptance boundary

This proves the actual Gazebo camera/ROS graph, exact installed semantic world,
simulation-only metric stop distance, dashboard preview freshness on this host,
and detector-to-CORE policy readback. It does not prove Pi/ARM64 behavior,
physical Pinky Pro camera mounting or homography, braking distance, motor
response, or unattended field acceptance. Those remain DEVICE and FIELD gates.
