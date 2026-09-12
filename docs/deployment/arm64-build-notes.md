# Rosy OS ARM64 build notes

This is the current Raspberry Pi 5 boundary for Rosy OS. The host is Raspberry
Pi OS Lite 64-bit; the ROS 2 Jazzy userland is built and run in the containers
defined by `deploy/robot/compose.yaml`.

## Source and container builds

For a development workspace, build the ROS packages from the repository root:

```bash
cd src
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
```

For the device image, build from `deploy/robot` after creating the installer
managed `.env`:

```bash
cd deploy/robot
docker compose --env-file .env build rosy-core
docker compose --env-file .env --profile motor build rosy-motor
docker compose --env-file .env --profile hardware build rosy-io
```

The image targets are intentionally separate. `rosy-core` owns the FastAPI and
`rclpy` middleware; `rosy-motor` is a motor commissioning path; `rosy-io` is the
full Pinky Pro motor, LiDAR, and Nav2 adapter path. Use `runtime-mode.sh` to
select a mode rather than starting containers by hand.

## Current package boundary

The absorbed `src/rosy_control` package is part of the Rosy OS source tree and
is covered by the host and ROS graph tests. Its pure sensing, OpenCV, planning,
calibration, and safety-policy code is reusable from the workspace. The current
device Dockerfile copies it into the `rosy-core` build for the explicitly
opt-in sensor adapter; the legacy full-stack launch is still not an operational
Compose mode. Do not enable that launch beside CORE because it can publish a
competing final `cmd_vel`. Camera/Picamera2 access and hardware launch wiring
remain separate transition gates.

The wiringPi/ws2811 based IMU, ADC, LCD, LED, and lamp drivers also remain
outside the first accepted device image until their Pi 5 compatibility and
physical tests pass. Their source packages may still be built in a workspace
where the required hardware dependencies are installed.

## ARM64 acceptance boundary

An ARM64 build is a build result only. Release acceptance additionally needs
the immutable image digest, Pi install/readback, runtime health, ROS graph and
deadman checks, and the physical Pinky Pro checklist in
`docs/deployment/pi5-acceptance-checklist.md`. Camera/OpenCV capture and any
OMX arm are separate hardware gates; this note does not advertise either as
ready.

The old upstream clone-and-delete instructions are retained in
`legacy-arm64-guide.md` for provenance only and must not be used for a Rosy OS
deployment.

## 2026-09-13 builder verification

Docker Desktop `desktop-linux` reports `linux/arm64`. The first real execution
probe and a clean `f0ba2cf` build failed with `exec format error`, which exposed
that the builder had no registered ARM64 emulator. Installing the `arm64`
binfmt handler and rerunning the probe produced `aarch64`.

The clean `ac81f2f` workspace then built
`rosy-core:arm64-validation-ac81f2f` successfully for `linux/arm64`:

```text
image ID: sha256:8aea3a0eaf9b20e0af27e70acc1e923c1830ac0577c2191a4ad9955637c02bd5
architecture: arm64
os: linux
```

The image entrypoint sources both ROS Jazzy and the Rosy workspace; through
that supported path, `python3` imported `rclpy`, OpenCV `4.6.0`, `rosy_core`,
and `rosy_control` and reported `aarch64`. A direct `--entrypoint python3`
probe is invalid because it bypasses the ROS environment setup.

This is a reproducible Core image candidate, not a release artifact. Keep
ARTIFACT at `HOLD` until the `io` image, manifest, signing, registry digest,
Pi install/readback, and physical checklist gates also pass.

The same clean workspace also built
`rosy-io:arm64-validation-ac81f2f` successfully. Its image ID is
`sha256:fcee5a58f657460f6b470cde94ada9c13692a48d38df4be51ec0083caa1f0622`
(`arm64/linux`, approximately 3.50 GB). The supported entrypoint path
registered `rclpy`, `sllidar_ros2`, and `rosy_bringup`; Python imported
OpenCV `4.6.0`, `serial`, and `dynamixel_sdk`; and both
`rosy_bringup/bringup_robot.launch.py --show-args` and
`rosy_navigation/hardware.launch.py --show-args` resolved successfully.

The IO image includes the full Nav2/LiDAR userland, but these checks do not
claim serial-device access, motor movement, map availability, or camera
capture. Those remain Device/FIELD gates.
