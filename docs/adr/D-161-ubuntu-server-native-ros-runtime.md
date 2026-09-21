## D-161 Ubuntu Server 24.04 + ROS 2 Jazzy 네이티브 제품 런타임으로 즉시 전환

**Date:** 2026-09-21

**Status:** Accepted

**Context:** ROS가 Pinky Pro 제품의 중심 런타임이다. ROS 2 Jazzy의 공식 Linux
바이너리 경로와 Raspberry Pi 5 장기 운영 기준을 함께 맞추려면 Ubuntu Server
24.04 LTS arm64를 제품 OS로 쓰는 편이 직접적이다. D-22의 Raspberry Pi OS 위
OCI 방식은 ROS 사용자 공간을 제공했지만 host OS, container runtime, ROS image를
동시에 운영하게 한다. 아직 승인된 제품 이미지나 현장 장치 증거가 없으므로 기존
방식을 더 누적하기보다 지금 전환하는 비용이 더 작다.

**Decision:** 다음을 즉시 제품 기준으로 적용한다.

1. Pinky Pro 제품 OS는 Ubuntu Server 24.04 LTS arm64이며, ROS 2 Jazzy는 공식
   Ubuntu deb 경로로 native 설치한다.
2. ROSY workspace는 native ARM64에서 빌드하고 모든 필수 패키지를
   `/opt/rosy/releases/<release-id>/install` 아래의 오프라인 colcon payload로
   이미지에 포함한다. 첫 부팅 때 인터넷에서 제품 패키지를 내려받지 않는다.
3. `rosy-core`, `rosy-io`, navigation 및 Host Agent는 systemd 서비스로 운영한다.
   `rosy-core`에는 장치 권한을 주지 않고 `rosy-io`에만 승인된 UART, I2C, SPI,
   GPIO, video 장치와 필요한 그룹을 열거한다.
4. D-22의 CORE/I/O 분리, 최종 `cmd_vel` 단일 발행자, 독립 motor deadman,
   navigation/hardware 승인 gate는 유지한다. D-161은 D-22의 runtime mechanism만
   supersede한다.
5. Docker와 Compose는 development and CI 전용이다. 제품 SD 이미지와 제품
   부팅 경로에는 container runtime을 설치하거나 요구하지 않는다.
6. 이미지 승격에는 official base-image digest, apt repository metadata, SBOM,
   ROSY source revision, 설치 패키지 inventory와 각 필수 패키지의
   `ros2 pkg prefix` readback이 필요하다.
7. source, 문서와 신규 제품 작업은 즉시 이 기준으로 전환한다. 다만 native
   ARM64 산출물과 실제 SD/Pi 증거가 생기기 전에는 ARTIFACT와 DEVICE 상태를
   계속 HOLD로 둔다.

**Alternatives:** Raspberry Pi OS + containers를 계속 제품 기준으로 유지하는 안은
ROS 중심 제품에 불필요한 운영 계층을 남겨 거절한다. Ubuntu와 Raspberry Pi OS를
동시에 제품 카드로 운영하는 안도 시험 행렬과 현장 복구 절차를 이중화하므로
거절한다. 공급사 이미지는 하드웨어 비교 baseline으로만 보존하며 제품 이미지로
승격하지 않는다.

**Consequences:** ROS 설치, rosdep, 진단과 vendor 문서의 기준이 Ubuntu/Jazzy로
정렬되고 product runtime에서 Docker 장애 표면이 사라진다. 반면 기존 Compose
서비스의 systemd 전환, 계정·장치 ACL 재검증, native ARM64 image build 및 실제
Pinky Pro 하드웨어 승인이 새 전환 gate가 된다. 문서 수용만으로 SD 카드가 준비된
것은 아니며, 검증되지 않은 입력을 채우기 전에는 writer를 실행하지 않는다.

**Validation / Transition:** `test_ubuntu_native_runtime_contract.py`가 OS, ROS,
runtime, 필수 패키지와 HOLD 상태를 고정한다. 후속 실행은 native service unit,
package inventory, release activation/rollback, first-boot personalization, 실제 SD
write/readback, Raspberry Pi boot, ROS graph 및 motor deadman 순서로 증거를 만든다.

**References:** D-22, D-154,
`docs/research/pinky-pro-software-requirements.md`,
`docs/plans/2026-09-21-ubuntu-native-ros-runtime-design.md`,
`docs/plans/2026-09-21-ubuntu-native-ros-runtime.md`.
