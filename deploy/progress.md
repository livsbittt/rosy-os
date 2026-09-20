---
module: deploy
logical_modules: [M01, M13, M14]
owner: 릴리스·플랫폼
last_verified: { commit: "c2bb799", date: 2026-09-21 }
gates:
  SOURCE:
    state: GO
    evidence: "native ARM64 unsigned payload builder와 Pinky G0-G5/release 경계 집중 516 passed, 8 skipped (2026-09-21)"
    cmd: "python3 -m pytest test/test_arm64_release_builder.py test/test_publication.py test/test_image_pipeline.py test/test_image_checks.py test/test_release_manifest.py test/test_release_signing.py test/test_release_bundle.py test/test_release_runtime.py test/test_release_updater.py test/test_release_layout.py test/test_release_boundary_guards.py test/test_pinky_commissioning.py test/test_device_readback.py test/test_robot_runtime.py -q"
  LOCAL:
    state: GO
    evidence: "1035 passed, 13 skipped (2026-09-21 Windows, commit c2bb799)"
    cmd: "python3 -m pytest test -q"
  ROS-SIM:
    state: N/A
  ARTIFACT:
    state: HOLD
    blocker: "native ARM64 builder는 구현됐지만 아직 aarch64 host에서 실행·offline 서명·검증된 bundle 발행 전"
  DEVICE:
    state: HOLD
    blocker: "Pi OS Lite bench Device의 install-pi.sh 설치, verify-pi.sh, device-readback.sh --json 증거 없음"
  FIELD:
    state: N/A
adrs: [D-22, D-26, D-30, D-33, D-36, D-46, D-53, D-124]
plans:
  - docs/plans/2026-09-01-rosy-os-v1-image-release-design.md
  - docs/plans/2026-09-08-release-delivery-design.md
  - docs/plans/2026-09-13-rosy-os-device-validation-implementation-plan.md
  - docs/plans/2026-09-15-module-harness-design.md
  - docs/plans/2026-09-21-pinky-device-commissioning-design.md
  - docs/plans/2026-09-21-native-arm64-release-builder-design.md
  - docs/plans/2026-09-21-native-arm64-release-builder.md
---
## 지금 상태

- Compose 기준선은 `core`/`motor`/`hardware` 프로필이다. vision·arm 프로필은 해당 Device 증거 전까지 추가하지 않는다.
- Device readback은 identity, activation/manifest digest, 서명 상태, core health, `cmd_vel` publisher 수를 secret 없는 JSON으로 수집하고 불일치 시 `device_runtime=HOLD`다.
- Pinky 커미셔닝 세션은 G0-G5 순서를 강제한다. G0-G2는 서명 stage/manifest,
  install/readback 원문에서 유도하며 G3-G5는 물리 측정 전 템플릿 상태로는 통과하지 않는다.
- binfmt 등록 후 ARM64 core/io 개발 후보 빌드와 import 확인까지 했다. 발행 가능한 artifact는 아니다.
- `arm64_release_builder.py`는 native Linux `aarch64`, ARM64 Docker daemon, clean full revision, digest-pinned ROS base만 허용하고 core/io의 linux/arm64·revision label·image ID를 검증한 뒤 비밀 없는 unsigned payload를 원자적으로 만든다. OCI archive는 검사된 immutable image ID에서 저장하며 서명은 기존 offline packager만 수행한다.
- `c2bb799`의 전체 host 회귀가 통과했다. 이 증거는 장치/물리 인수를 대신하지 않는다.

## 다음 gate

1. native aarch64 builder에서 unsigned payload를 만들고 offline key로 서명·publication 검증해 immutable bundle을 발행한다(ARTIFACT).
2. [첫 장치 런북](../docs/deployment/pinky-pro-first-device-runbook.md)의 G0-G5를
   SSH 또는 console에서 실행하고 session/raw evidence를 보존한다(DEVICE).

## 현재 유효한 금지사항

- `rosy_core` 안에 `nmcli`, `reboot`, compose 제어를 넣지 않는다. 호스트 권한은 Host Agent만 가진다(D-22).
- release 이미지는 x86 QEMU 결과로 발행하지 않는다.
- 로봇 identity에 기본값을 두지 않는다(D-33).
