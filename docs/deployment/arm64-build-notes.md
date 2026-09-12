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

Docker Desktop `desktop-linux` reports `linux/arm64`, but the actual execution
probe `docker run --rm --platform linux/arm64 alpine:3.20 uname -m` fails with
`exec format error`. A clean Rosy OS `f0ba2cf` build reaches the base image and
fails at the first ARM64 `RUN` step with the same error. This is evidence that
the current builder has no working QEMU/binfmt execution path; it is not an
ARM64 artifact. Keep ARTIFACT at `HOLD` until a native ARM64 builder or a
verified binfmt-enabled builder completes the `core`, `io`, manifest, signing,
and image-digest checks.
