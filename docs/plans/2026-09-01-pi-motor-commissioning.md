# Raspberry Pi 5 Motor Commissioning Implementation Plan

**Goal:** Add a rapid and safe Wi-Fi/UART/motor commissioning path without coupling early motor tests to LiDAR.

**Architecture:** Retain the core-only deployment default, add a motor-only Compose/runtime mode, configure and verify Pi 5 UART4, ping DYNAMIXEL devices without torque, verify dashboard reachability from Windows, and reuse the existing authenticated teleop API for hold-to-drive controls.

**Tech Stack:** Raspberry Pi OS Lite, NetworkManager, Bash, PowerShell/OpenSSH, Docker Compose, ROS 2 Jazzy, DYNAMIXEL SDK, FastAPI, vanilla HTML/CSS/JavaScript, pytest.

## Task 1: Commissioning contract tests

- Extend `test/test_pi_wifi_deployment.py` with failing contracts for UART4 configuration, motor-only runtime, torque-free ping, and peer HTTP acceptance.
- Extend dashboard tests with failing hold-to-drive and fail-to-zero contracts.
- Run the focused tests and retain the expected failures before implementation.

## Task 2: Parameterize the motor transport

- Add ROS launch arguments and node parameters for motor device, baudrate, and IDs.
- Replace the hard-coded bringup values while preserving current defaults.
- Add a motor-only launch entry that excludes LiDAR.
- Run bringup unit/static tests.

## Task 3: Add runtime modes and UART preflight

- Split Compose into `rosy-motor` and `rosy-lidar` services/profiles.
- Add `motor` to the runtime wrapper and environment template.
- Add an idempotent Pi UART4 configuration tool and a commissioning verifier with torque-free DYNAMIXEL ping.
- Ensure installer permissions include the new tools.
- Run shell syntax and focused contract tests.

## Task 4: Add Windows peer acceptance

- Extend the deployment helper or add a focused acceptance helper that verifies WLAN addresses and calls the Pi API/dashboard from Windows.
- Keep credentials out of output and preserve SSH host-key checks.
- Parse with the PowerShell AST and run focused contracts.

## Task 5: Add hold-to-drive dashboard control

- Add commissioning acknowledgement and four direction controls.
- Stream low-speed teleop only while pressed and issue zero on every release/focus/network failure path.
- Disable movement unless the latest state is MANUAL, safety is released, teleop capability is enabled, authentication exists, and acknowledgement is checked.
- Run dashboard tests and JavaScript syntax checks.

## Task 6: Documentation and full verification

- Update the Pi Wi-Fi/runtime runbooks with wiring-voltage warnings, exact commissioning order, and rollback to core.
- Run focused and full tests, syntax checks, Compose config, Docker builds, and diff checks.
- Keep physical Pi and motor acceptance as HOLD until the device is reachable and the recorded bench procedure passes.

