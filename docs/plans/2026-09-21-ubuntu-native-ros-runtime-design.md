# Ubuntu Native ROS Runtime Immediate Transition Design

**Date:** 2026-09-21

**Decision:** D-161 Accepted

**Target:** Pinky Pro / Raspberry Pi 5 / arm64

## Outcome

ROSY OS의 제품 경로는 지금부터 Ubuntu Server 24.04 LTS arm64와 native ROS 2
Jazzy만 사용한다. 이 immediate transition은 신규 구현과 산출물 계약의 기준을
즉시 바꾼다는 뜻이다. 아직 이미지가 만들어졌거나 현재 연결된 SD 카드에 기록되었다는
뜻은 아니다.

| Gate | Current state | Exit evidence |
|---|---|---|
| CONTRACT | GO | D-161, lock schema, executable contract test |
| ARTIFACT | HOLD | native ARM64 build, digest, SBOM, package inventory, signature |
| MEDIA | HOLD | explicit target selection, write, whole-device readback digest |
| BOOT | HOLD | Raspberry Pi 5 serial/boot journal and first-boot result |
| DEVICE | HOLD | ROS graph, hardware readback, motor deadman and stop evidence |
| FLEET | HOLD | two distinct robots, unique identity, isolated DDS and Fleet FAT/MAT |

## Product architecture

```text
Ubuntu Server 24.04 LTS arm64
├── /opt/ros/jazzy                         official native ROS debs
├── /opt/rosy/releases/<release-id>/install offline ROSY colcon payload
├── /opt/rosy/current -> releases/<id>      atomic release selector
├── rosy-core.service                       no device access; final cmd_vel owner
├── rosy-io.service                         enumerated UART/I2C/SPI/GPIO/video only
├── rosy-navigation.service                 disabled until hardware approval
├── rosy-host-agent.service                 separate privileged command boundary
└── NetworkManager + first-boot provisioner D-154 identity/network application
```

The service boundary replaces the D-22 container mechanism, not its safety intent.
CORE remains the only operational final-command owner. I/O independently drives zero
RPM after the deadman timeout. Navigation and hardware overlays remain fail-closed.

## Image construction

The release build runs on a native ARM64 host:

1. Fetch the exact official Ubuntu Server 24.04 preinstalled arm64 Raspberry Pi image.
2. Verify its published SHA-256 and record the source URL.
3. Customize the offline filesystem without booting an untrusted product state.
4. Install pinned ROS 2 Jazzy debs and resolved system dependencies.
5. Build ROSY at the pinned source revision and stage the install tree under
   `/opt/rosy/releases/<release-id>/install`.
6. Install least-privilege users, systemd units, network and first-boot contracts.
7. Emit OS/apt metadata, SBOM, source revision and ROS package inventory.
8. Scan for build-time secrets, sign the manifest, then run artifact verification.

x86/QEMU builds remain useful for development but cannot produce a releasable image.

## Mandatory Pinky Pro payload

The image must contain at least these ROS packages: `interfaces`, `core`, `bringup`,
`description`, `navigation`, `control`, `omx_adapter`, `led`, `sensor_adc`,
`lamp_control`, `emotion`, and `imu_bno055`. Success requires both an inventory entry
and a clean-environment `ros2 pkg prefix <package>` readback for every required package.
No required product package may be deferred to first-boot internet access.

## Runtime users and privileges

- `rosy-core` owns API/state/command arbitration and receives no device nodes.
- `rosy-io` receives only board-profile device nodes and required supplemental groups.
- The interactive login account is distinct from both service accounts.
- Host Agent retains its authenticated local socket boundary; CORE does not gain shell,
  arbitrary systemd, package-manager, reboot or NetworkManager authority.
- Unit hardening and device allowlists are release-tested, not inferred from unit text.

## Device identity, networking and fleet

D-154 remains authoritative. A common image is personalized per SD card with a random
four-character hostname in the `rosy-pinky-xxxx` family, immutable `device_uid`, and
separately protected bootstrap credentials. The supplied Wi-Fi credentials are inputs
to the encrypted/permission-restricted provisioning flow and must never appear in Git,
logs, manifests or command output.

Fleet readiness is not implied by a hostname. Each robot must prove unique identity,
site enrollment, outbound control-plane connectivity, ROS domain isolation, heartbeat,
mission handling and emergency-stop behavior. Two-robot physical evidence is required
before FLEET can become GO.

## Docker boundary

Dockerfiles and Compose may remain for developer workstations and CI while native
services are implemented. They are excluded from the product image, product boot path
and field recovery contract. Any document that describes Docker as the product runtime
is superseded by D-161.

## Migration and rollback

All new product-runtime changes target Ubuntu/native immediately. Existing container
tests remain useful as development checks but do not satisfy release acceptance. Image
rollback selects a previously signed `/opt/rosy/releases/<id>` payload or rewrites a
previously accepted full image; it never mixes an old container runtime into the new
product baseline.

Until the implementation plan produces all named evidence, ARTIFACT remains HOLD and
DEVICE remains HOLD. The connected SD card must not be overwritten merely because this
design is accepted.
