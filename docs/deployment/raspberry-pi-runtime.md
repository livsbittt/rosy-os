# Raspberry Pi 5 Robot Runtime

**Target:** Raspberry Pi 5 8GB, Raspberry Pi OS Lite 64-bit, ROSY Phase 1

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

1. Install Raspberry Pi OS Lite 64-bit and apply system updates.
2. Install Docker Engine and the Compose plugin using Docker's Debian arm64
   instructions.
3. Enable the required UARTs in the Raspberry Pi boot configuration. Disable
   the login console on UARTs assigned to the robot.
4. Verify the real device nodes; do not assume numbering from another Pi:

   ```bash
   ls -l /dev/ttyAMA0 /dev/ttyAMA4
   getent group dialout
   id rosy
   ```

5. Install this repository at `/opt/rosy` and create the protected robot
   configuration:

   ```bash
   sudo install -d -o rosy -g rosy /opt/rosy /var/lib/rosy
   sudo install -d -o root -g rosy /etc/rosy
   sudo cp deploy/robot/config/rosy.pi5.example.yaml /etc/rosy/rosy.yaml
   sudo chown root:rosy /etc/rosy/rosy.yaml
   sudo chmod 0640 /etc/rosy/rosy.yaml
   ```

Replace every development API token in `/etc/rosy/rosy.yaml` before connecting
the robot to a network.

## 3. Runtime configuration

```bash
cd /opt/rosy/deploy/robot
cp .env.example .env
```

Set the robot identity, per-robot `ROS_DOMAIN_ID`, actual UART paths, service
UID/GID, `ROSY_DATA_PATH`, and `dialout` GID in `.env`. The data directory must
be owned by that UID/GID (`sudo chown -R <uid>:<gid> /var/lib/rosy`). Do not use
`privileged: true`. Only `rosy-io` receives the two UART devices.

`ROSY_NAMESPACE` is also applied to the core TF frame prefix, so topics and
frames stay aligned. The mounted Pi 5 Lite profile advertises only the motor,
encoder, LiDAR, teleop, and event functions present in this first slice; IMU,
battery, Nav2 goals, SLAM, and swarm remain disabled until their runtimes are
packaged and physically accepted.

For a released robot, replace development image tags with immutable image
digests that were built and accepted for the exact source revision.

## 4. Build and start

```bash
cd /opt/rosy/deploy/robot
docker compose --env-file .env --profile hardware build
docker compose --env-file .env --profile hardware up -d
docker compose --env-file .env --profile hardware ps
docker compose --env-file .env logs --tail 100 rosy-core rosy-io
```

Install boot-time supervision after the interactive run succeeds:

```bash
sudo install -m 0644 rosy-runtime.service /etc/systemd/system/rosy-runtime.service
sudo systemctl daemon-reload
sudo systemctl enable --now rosy-runtime.service
systemctl status rosy-runtime.service
```

Docker restart policies own container restarts. The systemd unit owns only the
whole Compose application lifecycle; it must not also restart individual
containers.

## 5. Physical acceptance gates

Run tests with the wheels lifted before any floor test.

| Gate | Procedure | Pass evidence |
|---|---|---|
| Configuration | `docker compose --profile hardware config` | two services; only `rosy-io` has devices; neither is privileged |
| Core health | query `/api/v1` and authenticated `/api/v1/robot/state` | healthy container; state stream at least 5 Hz |
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

## 6. Stop and rollback

```bash
cd /opt/rosy/deploy/robot
docker compose --env-file .env --profile hardware down --timeout 10
```

For an image rollback, set `ROSY_CORE_IMAGE` and `ROSY_IO_IMAGE` to the last
accepted digests, run `docker compose pull`, then start the hardware profile.
Never roll back the robot configuration or waypoint data implicitly with the
container image.
