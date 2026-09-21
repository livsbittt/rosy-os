# Semantic road control host simulation (2026-09-21)

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
- `semantic_road_simulation.svg`: state/command timeline.
- `camera_detection_montage.png`: the synthetic camera inputs used by the
  production detector.
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

## Acceptance boundary

This is a deterministic Windows host simulation. It proves the semantic map
asset and the ROS-free perception-policy-command chain. It does not prove a
running Gazebo camera/ROS graph, Pi/ARM64 artifact, physical Pinky Pro camera
mount or homography, braking distance, motor response, or unattended field
acceptance. Those remain ROS-SIM, DEVICE, and FIELD gates respectively.
