---
module: deploy
logical_modules: [M01, M13, M14]
owner: 릴리스·플랫폼
last_verified: { commit: "b98642f", date: 2026-09-20 }
gates:
  SOURCE:
    state: GO
    evidence: "identity·runtime 계약 시험 통과 (2026-09-15 test/ suite 실행에 포함)"
    cmd: "python3 -m pytest test/test_dds_identity_contracts.py test/test_robot_runtime.py -q"
  LOCAL:
    state: GO
    evidence: "835 passed, 12 skipped (2026-09-15 Windows + Git Bash/OpenSSL, 미커밋 WIP 포함 작업 트리)"
    cmd: "python3 -m pytest test -q"
  ROS-SIM:
    state: N/A
  ARTIFACT:
    state: HOLD
    blocker: "ARM64 개발 후보(ac81f2f core/io)만 존재. 서명 manifest·OCI archive·immutable registry digest 발행 전"
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
---
## 지금 상태

- Compose 기준선은 `core`/`motor`/`hardware` 프로필이다. vision·arm 프로필은 해당 Device 증거 전까지 추가하지 않는다.
- Device readback은 identity, activation/manifest digest, 서명 상태, core health, `cmd_vel` publisher 수를 secret 없는 JSON으로 수집하고 불일치 시 `device_runtime=HOLD`다.
- binfmt 등록 후 ARM64 core/io 개발 후보 빌드와 import 확인까지 했다. 발행 가능한 artifact는 아니다.
- 작업 트리에 미커밋 변경이 있다(Dockerfile, compose, install-pi.sh, `.env.example`, motion profile). LOCAL 증거는 이 작업 트리 기준이다.

## 다음 gate

1. native 또는 승인된 builder에서 서명 manifest와 immutable digest 발행(ARTIFACT).
2. SSH 가능한 Pi bench Device 설치 후 readback JSON 보존(DEVICE). 물리 센서·모터·OMX gate는 그 뒤 별도다.

## 현재 유효한 금지사항

- `rosy_core` 안에 `nmcli`, `reboot`, compose 제어를 넣지 않는다. 호스트 권한은 Host Agent만 가진다(D-22).
- release 이미지는 x86 QEMU 결과로 발행하지 않는다.
- 로봇 identity에 기본값을 두지 않는다(D-33).
