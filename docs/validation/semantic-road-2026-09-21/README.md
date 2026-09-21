# Semantic road control validation (2026-09-21)

## Actual Gazebo runtime result

`GAZEBO_CAMERA_GRAPH_PASS` / `CONTINUOUS_REALTIME_PREVIEW_HOLD`

WSL2 Ubuntu 24.04, ROS 2 Jazzy, Gazebo Harmonic 8.11.0에서 실제
`semantic_road_dashboard.launch.py gazebo_gui:=false`를 실행했다. Gazebo가
설치된 `map_260905_traffic.world`를 로드했고, 소스와 설치본의 SHA-256이
일치했다. 전체 digest는 `gazebo_runtime_result.json`에 기록했다.
`description`은 이제 `gz_sim` 런타임 의존성으로 자동 빌드된다.

실제 `/camera/front` 프레임은 `GAZEBO`, `front_camera_link`, 640x360으로
수신됐다. production road detector가 정지선을 confidence
`0.8141533745659723`로 검출했고, observation은
`map_260905_update_v2` / `road-scene-v1`을 보고했다. CORE는 검증된
homography가 없어 거리 산출을 하지 않고 `stop_distance_unavailable`,
`linear_scale=0.0`, 실제 속도 0으로 fail-closed 했다.

![Actual Gazebo front camera frame](gazebo_camera_frame.jpg)

이 PC의 WSL 렌더링에서는 실제 카메라 wall rate가 약 0.59~0.80 Hz,
dashboard preview가 약 0.36 Hz라 프레임이 간헐적으로 stale이 되었다.
안전 타임아웃을 느슨하게 만들지 않았으며, 실시간 연속 주행과 실제 Pinky Pro
카메라/모터 검증은 여전히 HOLD다. 전체 수치와 gate는
`gazebo_runtime_result.json`에 기록했다.

## Result

`SEMANTIC_ROAD_HOST_SIM_PASS`

The `map_260905_update_v2` geometry is preserved and a derived semantic road
scene adds one lane, one stop line, one crosswalk, and one traffic signal. The
host simulation renders camera frames and passes them through the production
road detector, strict bridge decoder, line-follow manager, traffic policy, and
the atomic command gate immediately before the sole CORE Command Manager.

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

- `result.json`: machine-readable policy and command samples.
- `gazebo_runtime_result.json`: actual Gazebo camera, detector, and CORE
  readback with explicit remaining HOLD gates.
- `gazebo_camera_frame.jpg`: actual Gazebo `/camera/front` frame pulled from
  the authenticated CORE preview endpoint; this is not a HOST-SIM fixture.
- `semantic_road_simulation.svg`: state/command timeline.
- `camera_detection_montage.png`: the synthetic camera inputs used by the
  production detector.
- `camera_preview_demo.jpg`: one HOST-SIM camera frame with the same semantic
  overlay published to the dashboard preview topic.
- `camera_preview_simulation.gif`: six HOST-SIM camera frames played as a
  preview animation. This demonstrates the UI input shape, not Gazebo runtime.
- `camera_live_dashboard.png`: Chromium rendering of the camera panel and map
  together, using the HOST-SIM preview fixture. It shows the source capture
  clock separately from local receipt latency.
- `traffic_policy_dashboard.png`: Chromium evidence of the applied
  `ENFORCED` policy, active revision, evidence readback, tunable thresholds,
  and simulation-only signal controls.
- `src/apps/control/map/map_260905_update_v2/review/map_260905_traffic.png`:
  semantic overlay on the measured 16-wall map.
- `src/apps/control/map/map_260905_update_v2/worlds/map_260905_traffic.world`:
  derived Gazebo world with lane, crosswalk, stop line, and signal models.

## Reproduce

From the repository root:

```powershell
python src/apps/control/tools/simulate_semantic_road.py `
  --output docs/validation/semantic-road-2026-09-21
python -m pytest `
  src/apps/control/test/test_semantic_road_simulation.py `
  src/apps/control/map/map_260905_update_v2/tests/test_road_scene.py -q
```

On a ROS 2 Jazzy host with Gazebo installed, run the real simulated camera path:

```bash
ros2 launch gz_sim semantic_road_dashboard.launch.py gazebo_gui:=false
```

Gazebo 창도 함께 보려면 `gazebo_gui:=true`로 바꾼다. 대시보드 검증에는
headless가 기본값이므로 GUI 창 종료가 전체 시뮬레이션을 끝내지 않는다.

Then open `http://127.0.0.1:8080/dashboard`, enter the Viewer token, and check
that the camera source reads `GAZEBO`. The checked-in screenshot is deliberately
labelled `HOST-SIM`; it proves the browser/dashboard rendering without claiming
that Gazebo was running on this Windows host.

The browser fixture also verifies that status sequence 7 is requested as
`frame?sequence=7`, the JPEG response returns the same sequence header, and a
failed reauthentication clears the old frame and stops camera polling.

## Acceptance boundary

The host fixtures still prove the deterministic ROS-free chain. The additional
runtime evidence now proves the actual Gazebo camera/ROS graph, the exact
installed semantic world identity, and fail-closed detector-to-CORE policy
readback. It does not prove sustained realtime camera throughput, Pi/ARM64
artifact behavior, physical Pinky Pro camera mount or homography, braking
distance, motor response, or unattended field acceptance. Those remain
separate performance, DEVICE, and FIELD gates.
