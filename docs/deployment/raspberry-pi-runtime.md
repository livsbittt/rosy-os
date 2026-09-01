# Raspberry Pi 5 Robot Runtime

**Target:** Raspberry Pi 5 8GB, Raspberry Pi OS Lite 64-bit, ROSY Phase 1

유선 LAN 없이 SD 카드를 굽고 Wi-Fi로 설치·접속하는 전체 절차는
[Rosy Raspberry Pi 5 Wi-Fi 배포 가이드](raspberry-pi-wifi-image.md)를 먼저
따른다. 이 문서는 하드웨어 런타임과 물리 승인 항목을 상세히 설명한다.

This deployment keeps Raspberry Pi OS as the host and runs the ROS 2 Jazzy
userland in two containers. `rosy-core` owns the FastAPI/rclpy middleware and
has no device access. `rosy-io` owns the Pinky Pro motor and LiDAR adapters.

> This first runtime slice does not yet package the wiringPi/ws2811 based IMU,
> ADC, LCD, LED, or lamp nodes. Those drivers need a separate Raspberry Pi 5
> compatibility port and physical verification before device access is added.
> The robot-side image also omits the 32 MB visualization meshes; an operator
> workstation that runs RViz should keep the full `rosy_description` package.

## 1. Safety boundary

`rosy_core` publishes the final `cmd_vel`. `rosy_bringup` consumes it and
controls the Dynamixel bus. The driver-side command deadman requests zero RPM
after a 500 ms stale-command threshold and keeps retrying until the driver
accepts the stop. The 30 Hz polling loop adds up to about 34 ms plus serial and
scheduler latency, which must be measured on the Pi. This check is inside
`rosy-io`, so it still runs when FastAPI, `rosy-core`, or DDS fails.

The software deadman is not a safety-certified stop. A hazardous deployment
still needs a hardware E-stop and, where the risk assessment requires it, an
independent controller/watchdog outside the Raspberry Pi.

## 2. Host preparation

1. Follow the [Wi-Fi deployment guide](raspberry-pi-wifi-image.md) to flash
   Raspberry Pi OS Lite 64-bit, configure SSH/Wi-Fi, and run the versioned
   installer. The installer owns `/opt/rosy` as `root:root`; do not change that
   tree to the login user's ownership because systemd executes its runtime
   wrapper as root.
2. Enable the required UARTs in the Raspberry Pi boot configuration. Disable
   the login console on UARTs assigned to the robot.
3. Verify the real device nodes; do not assume numbering from another Pi:

   ```bash
   ls -l /dev/ttyAMA0 /dev/ttyAMA4
   getent group dialout
   id rosy
   ```

The installer creates `/etc/rosy/rosy.yaml` with device-local tokens and mode
`0640`, preserving and revalidating it on later runs. Do not copy the example
configuration over that file. Retrieve the one-time credential handoff as
described in the Wi-Fi guide.

## 3. Runtime configuration

Edit the installer-managed environment as root:

```bash
sudoedit /opt/rosy/deploy/robot/.env
```

Set the robot identity, per-robot `ROS_DOMAIN_ID`, actual UART paths, and image
pins in `.env`. The installer manages service UID/GID, `ROSY_DATA_PATH`,
`dialout` GID, file ownership, and the safe `ROSY_RUNTIME_MODE=core` default.
Do not use `privileged: true`. Only `rosy-io` receives the two UART devices.

`ROSY_NAMESPACE` is also applied to the core TF frame prefix, so topics and
frames stay aligned. The mounted Pi 5 Lite profile advertises only the motor,
encoder, LiDAR, teleop, and event functions present in this first slice; IMU,
battery, Nav2 goals, SLAM, and swarm remain disabled until their runtimes are
packaged and physically accepted.

For a released robot, replace development image tags with immutable image
digests that were built and accepted for the exact source revision.

## 4. Build and start

Keep `ROSY_RUNTIME_MODE=core` until the physical gates below are accepted. To
prepare and promote the hardware profile afterward:

```bash
cd /opt/rosy/deploy/robot
sudo docker compose --env-file .env --profile hardware build
sudoedit /opt/rosy/deploy/robot/.env
# Set ROSY_RUNTIME_MODE=hardware, save, then:
sudo systemctl restart rosy-runtime.service
sudo docker compose --env-file .env --profile hardware ps
sudo docker compose --env-file .env logs --tail 100 rosy-core rosy-io
```

The installer already installs boot-time supervision. Verify it after the
interactive checks:

```bash
systemctl is-enabled rosy-runtime.service
systemctl status rosy-runtime.service
```

Docker restart policies own container restarts. The systemd unit owns only the
whole Compose application lifecycle; it must not also restart individual
containers.

## 5. Rosy OS dashboard

Open the dashboard from a machine on the robot network:

```text
http://<raspberry-pi-ip>:8080/dashboard
```

Enter a configured viewer, operator, or administrator API token. The token is
stored only in the browser tab's `sessionStorage`; closing the tab removes it.
Viewer can inspect all dashboard status and trigger the safety stop, operator
can also change robot mode, and only administrator can release an emergency
stop. API authorization remains authoritative even if a UI control is visible.

The dashboard reads host telemetry through these bounded read-only mounts:
`/proc/{uptime,loadavg,stat,meminfo}`, `/sys/class/thermal`, its sysfs target
`/sys/devices/virtual/thermal`, `/etc/os-release`, and `/etc/hostname`. It does not mount the host root,
Docker socket, systemd control socket, or any additional device. Missing host
files appear as unavailable fields instead of failing `rosy-core`.

Mode changes require confirmation in the dashboard and are serialized while a
request is in flight. The NAV button is disabled when
`navigation.goal_navigation` is unavailable; the API enforces the same gate.
Navigation velocity samples expire after 500 ms, so changing modes cannot
reactivate an old motion sample.

Useful checks:

```bash
curl http://127.0.0.1:8080/dashboard
curl -H 'Authorization: Bearer <viewer-token>' \
  http://127.0.0.1:8080/api/v1/system/runtime
```

Do not place tokens in shell history on production equipment; the commands
above are diagnostic examples. Use a protected environment or interactive
prompt when collecting real evidence.

## 6. Physical acceptance gates

Run tests with the wheels lifted before any floor test.

| Gate | Procedure | Pass evidence |
|---|---|---|
| Configuration | `docker compose --profile hardware config` | two services; only `rosy-io` has devices; neither is privileged |
| Core health | query `/api/v1` and authenticated `/api/v1/robot/state` | healthy container; state stream at least 5 Hz |
| Dashboard | open `/dashboard`, authenticate, then inspect `/api/v1/system/runtime` | UI loads without external assets; Pi OS/CPU/RAM/disk/temp values agree with host commands or are explicitly unavailable |
| Motor command | send a bounded low-speed command | expected wheel direction and RPM |
| Driver deadman | stop `rosy-core` while wheels turn | measured stop latency is recorded and meets the site safety requirement; expected software threshold is 500 ms plus poll/serial latency |
| DDS loss | temporarily give `rosy-core` a different domain | `rosy-io` stops the motors within the timeout |
| I/O failure | stop `rosy-io` while wheels turn | orderly shutdown sends zero RPM and disables torque |
| Abrupt failure | kill `rosy-io` with `SIGKILL` | hardware E-stop/controller prevents persistent motion; otherwise HOLD |
| UART removal | disconnect each test adapter safely | no uncontrolled motion; error is visible and restart is bounded |
| Boot recovery | reboot the Pi | both services return; no motion before a fresh command |
| API latency | measure normal-load requests | p95 internal processing target at or below 100 ms |
| Thermal/resource | run navigation workload for 30 minutes | state at least 5 Hz; no sustained thermal throttling; record CPU/RAM/temp |
| Storage | inspect Docker and journal growth after endurance run | local log rotation active; projected SD-card use is acceptable |

The deployment gate remains **HOLD** until the physical deadman, abrupt-failure,
UART, boot, thermal, and storage rows have recorded device evidence.

## 7. Stop and rollback

```bash
cd /opt/rosy/deploy/robot
sudo docker compose --env-file .env --profile hardware down --timeout 10
```

For an image rollback, set `ROSY_CORE_IMAGE` and `ROSY_IO_IMAGE` to the last
accepted digests, run `docker compose pull`, then start the hardware profile.
Never roll back the robot configuration or waypoint data implicitly with the
container image.
