# Pinky Pro hardware mapping G5 design

**Date:** 2026-09-21
**Status:** Accepted for implementation
**Scope:** real Pinky Pro G5 mapping and evidence capture

## Problem

The commissioning runbook calls the SLAM API in G5, but the deployed
`hardware` graph launches localization (`map_server` + AMCL) only. The device
capability file correctly advertises `slam: false`, the IO image does not
install SLAM Toolbox, and the maps mount is read-only. A real device therefore
cannot complete the documented G5 map-save sequence.

The existing G5 evidence also proves only an API response. It does not retain
the raw sensor/TF stream or the actual map YAML/image pair required to audit a
physical mapping run.

## Decision

Keep `ROSY_RUNTIME_MODE=hardware` as the board/runtime identity and add an
orthogonal, fail-closed navigation backend:

- `ROSY_NAVIGATION_BACKEND=localization` is the default and preserves the
  current AMCL + map-server graph, `slam: false`, and a read-only maps mount.
- `ROSY_NAVIGATION_BACKEND=slam` launches Nav2 navigation + SLAM Toolbox,
  advertises `slam: true`, selects a SLAM-specific readiness profile, and makes
  only `/var/lib/rosy/maps` and `/var/lib/rosy/commissioning` writable.
- `slam` is valid only with `hardware`; `core` and `motor` reject it before
  Docker Compose is invoked.
- The launch layer validates the backend independently. Mapping does not
  require an existing occupancy map and localization does not start SLAM.
- Map-save names are reduced to a safe basename and resolved beneath
  `/var/lib/rosy/maps`. CORE and the IO container see the same host directory,
  so the returned map id hashes the actual `.pgm` bytes.
- G5 records a bounded MCAP rosbag containing scan, odometry, velocity, map and
  TF topics. It also copies and hashes the saved `.yaml`/`.pgm` pair. These
  artifacts are distinct from the operator-authored G5 body.

## Runtime graph

| Backend | Localization nodes | SLAM Toolbox | Map mount | Capability |
|---|---|---|---|---|
| `localization` | `map_server`, AMCL, Nav2 | off | read-only | `slam: false` |
| `slam` | Nav2 only | online sync mapping | read-write | `slam: true` |

Both graphs retain the same motor/LiDAR bringup and the sole final velocity
publisher contract. A backend switch is a runtime restart, never an in-process
graph mutation.

## Readiness

Localization requires AMCL, map server, controller, both costmaps, and the
motor-adapter lease. Mapping replaces AMCL/map-server with the active
`slam_toolbox` lifecycle node. Motion remains zero while any required evidence
is absent or stale according to the existing readiness rules.

## Evidence and acceptance

Host tests prove configuration refusal paths, graph selection, packaging,
safe map paths, and G5 manifest requirements. A Docker/launch smoke test may
prove the image graph on the host, but only the physical run can change DEVICE
or FIELD from HOLD.

Physical G5 is GO only when the session contains:

1. fresh LiDAR and bounded MCAP telemetry;
2. the real saved map YAML and image with hashes;
3. a successful controlled navigation goal with no collision;
4. final `estop=true` and zero linear/angular velocity.
