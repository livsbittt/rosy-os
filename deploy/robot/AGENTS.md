<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-16 -->

# robot

## Purpose

On-device runtime: multi-stage Dockerfile (`core` / `io` targets), Compose `rosy-runtime`, systemd units, Pi install and Windows deploy/verify scripts. `rosy-core` is FastAPI/rclpy only; motors and LiDAR are separate services (D-22). Slice catalog (`config/board.yaml`): **CORE required**; motor/io/nav install as existing modes; vision/omx/ai are catalog-only and stay dark.

## Key Files

| File | Description |
|------|-------------|
| `Dockerfile` | Multi-stage: `core` image vs `rosy-io` |
| `compose.yaml` | `rosy-core` (always), `rosy-motor` (profile `motor`), hardware/LiDAR/Nav2 (profile `hardware`); host network, read-only, cap_drop ALL |
| `runtime-mode.sh` | Modes: `core` \| `motor` \| `hardware` (not `io`) |
| `entrypoint.sh` | Container entry |
| `install-pi.sh` | First-boot install on Pi. `--preset` (mode/alias) or `--slices` (must match a preset, include `core`); both map to `ROSY_RUNTIME_MODE`. vision/omx/ai: not installable yet |
| `configure-uart-pi5.sh` | Pi 5 UART (`ttyAMA4` for Dynamixel) |
| `deploy-from-windows.ps1` | Copy/deploy from a Windows host |
| `verify-from-windows.ps1` | Read-only remote peer verify; optional bounded batch SSH and atomic GO/HOLD JSON connection evidence |
| `verify-pi.sh` / `verify-motors.sh` / `verify-power.sh` | On-device checks. `verify-motors.sh` refuses to probe the UART whenever it cannot establish that the motor runtime is down — a compose failure counts, so missing docker or an unset identity now stops it rather than opening the gate |
| `device-readback.py` / `device-readback.sh` | Secret-free JSON evidence for OS identity, activation manifest, core health, and ROS graph |
| `commission-pinky.py` / `commissioning_session.py` | Ordered G0-G5 evidence recorder; operator procedure is `docs/deployment/pinky-pro-first-device-runbook.md` |
| `measure-dds-baseline.sh` | Phase 0 DDS baseline (D-34). Requires `hardware` mode; records each topic's pre-attach subscriber count because attaching `ros2 topic bw` creates the traffic it measures |
| `rosy-runtime.service` | systemd unit for compose runtime |
| `rosy-lowbatt-shutdown.service` / `.path` / `.sh` | D-27: host watches CORE sentinel file and halts |
| `rosy-release-recover.service` / `release-recover.sh` | Failed-release recovery |
| `requirements-core.txt` / `requirements-io.txt` | pip constraints per image |
| `.env.example` | Compose env template (do not commit secrets) |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `config/` | Pi 5 lite profile, capabilities, example rosy.yaml (see `config/AGENTS.md`) |

## For AI Agents

### Working In This Directory

- Healthcheck: `GET http://127.0.0.1:8080/api/v1`.
- CORE is the only required slice. vision/omx/ai are catalogued with `enabled: false` and no compose service; do not start them.
- `rosy-core` has **no** `/dev` devices and no Docker socket. Do not add them.
- Host proc/sys bind-mounts are read-only for dashboard telemetry (`ROSY_HOST_ROOT=/host`).
- Low-battery shutdown: CORE writes `battery-shutdown-request.json`; the host unit executes halt (sentinel age 900 s, grace cap 600 s). CORE must not call shutdown itself (D-27).
- `rosy-runtime.service` **Requires** `rosy-release-recover.service` — `Wants=` would make recovery advisory.
- `ROS_DOMAIN_ID` has **no default** — it is derived from `ROSY_ROBOT_NUMBER`
  (`40 + N`, namespace `rosy_%02d`) at install time and `compose.yaml` uses the
  `${VAR:?}` form so an unset identity stops the runtime (D-33). A default here is
  what shipped every unit as 42/`rosy_01`. CycloneDDS URI `file:///etc/rosy/cyclonedds.xml`.

### Testing Requirements

```bash
python3 -m pytest test/test_robot_runtime.py test/test_release_boundary_guards.py -v
```

### Common Patterns

Compose YAML anchors `x-ros-environment` and `x-runtime-defaults`. Namespace `__ns:=/${ROSY_NAMESPACE}`.

## Dependencies

### Internal

- Build context `../..` (repo root)
- Config overlays: `config/board.yaml` (`slices` / `presets`) plus `capabilities.{core,motor,hardware}.yaml`. `pi5-lite` is an alias resolved by `config/resolve-mode.sh`.

### External

- Docker Compose, systemd, Raspberry Pi OS

<!-- MANUAL: -->
