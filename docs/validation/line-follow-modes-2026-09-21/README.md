# D-143 IR / camera line-follow validation

Status: **HOST SIMULATION PASS / PHYSICAL DEVICE HOLD**

## What was exercised

- IR reflectance samples were normalized with independent black/white endpoints
  for left, centre, and right channels.
- Synthetic BGR frames exercised the same white-line camera detector used by the
  ROS observer.
- Both evidence streams passed through the selected-source CORE manager.
- Curves and lower confidence reduced linear speed; the configured 0.10 m/s cap
  was never exceeded.
- A stale sample stopped immediately. Continued loss latched `LOST` and emitted
  one `nav.lane_lost` event; a new observation did not auto-resume motion.

## Result

| Mode | Straight | Tightest simulated turn | Stale stop | Loss latch |
|---|---:|---:|---|---|
| IR_LINE | 0.08135 m/s | 0.04112 m/s | PASS | PASS |
| CAMERA_LINE | 0.03117 m/s | 0.01693 m/s | PASS | PASS |

Artifacts:

- `result.json`: deterministic samples and assertions
- `line_follow_simulation.svg`: speed response plot
- `dashboard_camera_line.png`: shipped dashboard markup with simulated camera
  tracking state

## Reproduce

```powershell
$env:PYTHONPATH="src/apps/control;src/core/core_common;src/core/core_events;src/core/core_features"
python src/apps/control/tools/simulate_line_follow.py `
  --output docs/validation/line-follow-modes-2026-09-21
```

On a ROS 2 host with the `control` package installed, the sensing-only observer
can be launched without adding another motion publisher:

```bash
ros2 launch control line_follow.launch.py namespace:=rosy_01 start_camera:=true
```

Before selecting `IR_LINE`, set `ir_calibration_enabled: true` only after
measuring all six black/white endpoint values in `config/line_follow.yaml`.

## Not yet proven

This host run does not prove Pinky Pro camera orientation/exposure, physical IR
polarity/endpoints, floor/line materials, ROS DDS timing, wheel response, or
safe driving clearance. Those remain device acceptance gates for the connected
robot.
