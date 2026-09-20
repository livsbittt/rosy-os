# Pinky Pro G3-G5 body templates

G0-G2 are derived by `commission-pinky.py prepare` from trusted tool output;
never author those bodies by hand. G3-G5 contain physical measurements and
observations, so the named operator fills these exact JSON bodies from the raw
telemetry. Replace every example measurement. Do not change a failure into a
passing value: leave the gate unrecorded and retain the raw files.

## G3 `stationary`

Capture the ten API states over at least two measured seconds. `sequence` is the
server state `seq`, not a hand-made row number.

```json
{
  "runtime_mode": "core",
  "cmd_vel_publishers": 1,
  "duration_s": 0.0,
  "samples": [
    {"sequence": 0, "mode": "UNMEASURED", "velocity": {"linear": null, "angular": null}, "safety": {"estop": false}}
  ]
}
```

## G4 `motor`

`stop_latency_s` is measured from command loss/release to confirmed zero. The
software gate rejects anything above 0.65 s; the site may impose a lower limit.

```json
{
  "operator": "OPERATOR_NAME",
  "wheels_lifted": true,
  "hardware_cut_reachable": true,
  "torque_free_preflight_passed": true,
  "configured_ids": [1, 2],
  "responded_ids": [1, 2],
  "deadman_trials": [
    {"direction": "forward", "trial": 1, "stop_latency_s": null, "final_velocity": {"linear": null, "angular": null}, "passed": false},
    {"direction": "forward", "trial": 2, "stop_latency_s": null, "final_velocity": {"linear": null, "angular": null}, "passed": false},
    {"direction": "reverse", "trial": 1, "stop_latency_s": null, "final_velocity": {"linear": null, "angular": null}, "passed": false},
    {"direction": "reverse", "trial": 2, "stop_latency_s": null, "final_velocity": {"linear": null, "angular": null}, "passed": false},
    {"direction": "cw", "trial": 1, "stop_latency_s": null, "final_velocity": {"linear": null, "angular": null}, "passed": false},
    {"direction": "cw", "trial": 2, "stop_latency_s": null, "final_velocity": {"linear": null, "angular": null}, "passed": false},
    {"direction": "ccw", "trial": 1, "stop_latency_s": null, "final_velocity": {"linear": null, "angular": null}, "passed": false},
    {"direction": "ccw", "trial": 2, "stop_latency_s": null, "final_velocity": {"linear": null, "angular": null}, "passed": false}
  ]
}
```

Create `G4-evidence-manifest.json` after hashing the eight distinct odometry
captures. Each entry repeats the matching `deadman_trials` value:

```json
{
  "schema_version": 1,
  "gate": "G4",
  "trials": [
    {"direction": "forward", "trial": 1, "stop_latency_s": null, "final_velocity": {"linear": null, "angular": null}, "passed": false, "evidence_sha256": "REPLACE_WITH_64_HEX"}
  ]
}
```

The final manifest must contain all eight direction/trial entries and eight
different digests that match eight supplied raw evidence files.

## G5 `hardware`

The map ID must identify this run's fresh physical map, not a Gazebo asset.

```json
{
  "operator": "OPERATOR_NAME",
  "runtime_mode": "hardware",
  "cmd_vel_publishers": 1,
  "lidar": {"fresh": true, "scan_hz": 0.0},
  "telemetry": {
    "format": "mcap",
    "duration_s": 0.0,
    "topics": ["/rosy_01/scan", "/rosy_01/odom", "/rosy_01/cmd_vel", "/rosy_01/map", "/tf", "/tf_static"],
    "mcap_sha256": "REPLACE_WITH_64_HEX",
    "metadata_sha256": "REPLACE_WITH_64_HEX"
  },
  "map": {
    "fresh": true,
    "map_id": "PHYSICAL_MAP_ID",
    "yaml_sha256": "REPLACE_WITH_64_HEX",
    "image_sha256": "REPLACE_WITH_64_HEX"
  },
  "navigation": {
    "goal_id": "PHYSICAL_GOAL_ID",
    "status": "SUCCEEDED",
    "collision_observed": false
  },
  "final_state": {
    "velocity": {"linear": 0.0, "angular": 0.0},
    "estop": true
  }
}
```

The example G5 `scan_hz` and `duration_s` values are intentionally invalid, so
an unmeasured template cannot pass. The MCAP must cover at least 30 seconds and
at most 30 minutes. Its two digests and the saved YAML/PGM digests must also be
present in the record's actual evidence-file digest set.

Create `G5-evidence-manifest.json` with five distinct role digests. Each
`value` must exactly equal the corresponding object in `G5-hardware.json`:

```json
{
  "schema_version": 1,
  "gate": "G5",
  "roles": {
    "lidar": {"value": {"fresh": true, "scan_hz": 0.0}, "evidence_sha256": "REPLACE_WITH_64_HEX"},
    "telemetry": {"value": {"format": "mcap", "duration_s": 0.0, "topics": ["/rosy_01/scan", "/rosy_01/odom", "/rosy_01/cmd_vel", "/rosy_01/map", "/tf", "/tf_static"], "mcap_sha256": "REPLACE_WITH_64_HEX", "metadata_sha256": "REPLACE_WITH_64_HEX"}, "evidence_sha256": "REPLACE_WITH_64_HEX"},
    "map": {"value": {"fresh": true, "map_id": "PHYSICAL_MAP_ID", "yaml_sha256": "REPLACE_WITH_64_HEX", "image_sha256": "REPLACE_WITH_64_HEX"}, "evidence_sha256": "REPLACE_WITH_64_HEX"},
    "navigation": {"value": {"goal_id": "PHYSICAL_GOAL_ID", "status": "SUCCEEDED", "collision_observed": false}, "evidence_sha256": "REPLACE_WITH_64_HEX"},
    "final_state": {"value": {"velocity": {"linear": 0.0, "angular": 0.0}, "estop": true}, "evidence_sha256": "REPLACE_WITH_64_HEX"}
  }
}
```
