# Pinky Pro Flashable Image Design

**Date:** 2026-09-22

**Decision:** D-163

**Target:** Raspberry Pi 5 / Pinky Pro / Ubuntu Server 24.04 LTS arm64 / ROS 2 Jazzy

## 1. Goal and non-goals

운영자가 release 폴더에서 파일 하나를 선택해 Raspberry Pi Imager로 microSD에 직접
기록할 수 있는 Rosy OS 제품 이미지를 만든다. 최종 image는 부팅 가능한 전체 disk
image이며 ROS와 Pinky Pro 필수 패키지를 첫 부팅 전부터 포함한다.

제품 산출물은 `.img.xz`다. 일반 PC installer ISO, 첫 부팅 package download,
장치별 완성 image, 제품 runtime의 Docker/Compose, x86 QEMU release build는 범위에서
제외한다. 전체 OS A/B update도 v1 범위가 아니다. 애플리케이션 release는 D-161의
`current`/`previous` 원자 전환으로 복구한다.

## 2. Approaches considered

### A. Canonical preinstalled Pi image를 native ARM64에서 수정 — 채택

Canonical의 `.img.xz`를 검증·해제하고 작업 사본의 partition을 mount한다. boot/root를
직접 구성하고 native chroot에서 apt/ROS 작업을 수행한 뒤 다시 `.img.xz`로 압축한다.
Pi firmware와 partition layout을 Canonical과 맞추면서 완성 media를 직접 기록할 수
있다. root 권한과 cleanup이 필요하지만 모든 단계를 검사 가능하게 만들 수 있다.

### B. Ubuntu installer ISO + unattended install — 기각

ISO는 현장 장비에서 installer를 다시 실행해야 하고 Raspberry Pi 전용 preinstalled
image 흐름과 다르다. 설치 시간·네트워크·입력에 따라 결과가 갈라져 공장 SD 생산과
checksum/readback 계약에 맞지 않는다.

### C. Ubuntu Core custom image — 이번 범위에서 기각

원자적 OS update 장점은 있지만 snap model, gadget/kernel, confinement와 release
ownership을 새로 설계해야 한다. D-161의 Ubuntu Server + native Jazzy 결정을 다시
여는 별도 ADR이 필요하다.

## 3. Artifact contract

한 release directory는 다음을 정확히 포함한다.

```text
dist/<release-id>/
  rosy-os-pinky-pro-<release-id>-arm64.img.xz
  manifest.json
  SHA256SUMS
  SHA256SUMS.sig
  sbom.spdx.json
  deb-packages.txt
  rosy-packages.txt
  required-ros-packages.txt
  source-revision.txt
  base-image-provenance.json
  build-provenance.json
  artifact-report.md
```

`.img` 작업 파일과 mount directory는 release directory 밖의 임시 작업 공간에 둔다.
성공·실패 모두 cleanup하고 성공 시에도 배포물에 포함하지 않는다. filename, release ID,
board, architecture, OS, runtime model, source revision과 모든 file hash는 manifest에
결속한다.

## 4. Build data flow

```text
Canonical .img.xz + signed checksum evidence
        │ verify exact locked input
        ▼
native aarch64 temporary raw .img
        │ expand + loop/partition mount
        ▼
boot partition ── device-neutral boot/first-boot files
root partition ── users + native Jazzy + ROSY payload + systemd
        │ offline package/readback checks
        ▼
unmounted raw .img ── filesystem check ── deterministic xz
        │ secret scan + SBOM + manifest + SHA256SUMS
        ▼
unsigned handoff ── offline Ed25519 signing ── signed release
        │ read-only artifact verification
        ▼
Windows PlanOnly ── explicit disk confirmation ── flash ── full readback
```

## 5. Image customization

Builder는 `uname -m=aarch64`, Ubuntu 24.04, clean pinned source revision, 검증된 lock을
먼저 확인한다. `xz -dc`로 base image를 임시 `.img`에 풀고 root partition 확장 여유를
확보한다. `losetup --find --show --partscan`으로 partition을 노출하고 boot/root를
각각 mount한다. trap은 역순으로 bind mount, filesystem mount와 loop device를
해제하며 cleanup 실패도 release 실패로 취급한다.

rootfs에는 고정 apt repository/key, ROS 2 Jazzy, NetworkManager, chrony와 요구된
Pinky ROS package가 설치된다. 별도 `rosy-core`/`rosy-io` 계정과 명시적 device group,
`/opt/rosy/releases/<id>`, immutable `/opt/rosy/native-runtime`, first-boot 도구와 unit을
설치한다. default target은 CORE only다. image 안에서 package inventory와
`ros2 pkg prefix`를 확인하고 network를 끈 상태에서도 필수 runtime 파일이 존재해야
한다.

cloud-init의 vendor default login은 제품 image에서 비활성화한다. 사용자 계정,
hostname, Wi-Fi와 Fleet 정보는 장치별 bundle 적용 전에는 존재하지 않는다. first-boot
unit만 boot partition의 `/rosy-provision/provision.json`을 읽을 준비 상태로 둔다.

## 6. Signing and Windows writer boundary

CI/native builder는 unsigned handoff까지만 만든다. secret scan을 통과한 파일에 대해
`SHA256SUMS`를 만들고 승인된 offline signing station이 Ed25519 signature를 생성한다.
공개키와 key ID는 repository의 승인된 trust store에 존재해야 한다.

Windows writer 입력은 개별 `ImageSignaturePath` 존재 여부가 아니라 signed release
directory, trusted public key와 정확한 image filename이다. writer는 공개키 검증,
manifest schema, release/board/architecture, signed checksum과 실제 image hash를 모두
확인한 뒤에만 disk probe를 시작한다. 따라서 잘못된 signature는 `PlanOnly`에서도
거절된다. 비밀 Wi-Fi 값은 그 이후 DPAPI profile에서 메모리로 읽어 one-shot bundle에
만 사용한다.

## 7. Acceptance gates

| Gate | Required evidence |
|---|---|
| SOURCE | contracts, builder cleanup/error tests, no ISO/product Docker path |
| ARTIFACT | native ARM64 build, signed manifest/checksums, SBOM, read-only mount inspection |
| MEDIA | exact disk identity, successful write, full-device readback match |
| BOOT | Ubuntu/Pi boot, first-boot completion, reboot and power-loss recovery |
| DEVICE | ROS package readback, graph, ACL, single `cmd_vel`, deadman |
| FLEET | two distinct Pinky identities, enrollment, heartbeat, commands, reconnect, safe loss |

앞 gate가 뒤 gate를 대신하지 않는다. 특히 `.img.xz` 파일이 존재하는 것만으로
ARTIFACT 또는 MEDIA GO가 아니다.

## 8. Failure behavior

- input digest/signature mismatch: mount 전에 중단
- non-aarch64 host 또는 dirty revision: output directory 생성 전에 중단
- mount/chroot/package failure: trap cleanup, partial release 삭제, cache 보존
- secret scan/SBOM/manifest failure: unsigned handoff를 노출하지 않음
- offline signature mismatch: Windows disk discovery 전에 중단
- disk identity drift: writer 호출 전에 중단
- write/readback mismatch: MEDIA HOLD, card 격리, Pinky에 삽입하지 않음
- first-boot bundle/Wi-Fi failure: CORE gate 폐쇄, motor off, repairable bundle 보존

## 9. Future extension

같은 `.img.xz`와 signed metadata를 Raspberry Pi Imager 2.x custom repository JSON으로
노출할 수 있다. catalog는 URL, release metadata와 hash를 편하게 전달할 뿐 trust
root가 아니다. v1은 로컬 signed release directory와 Windows writer를 기준 경로로
유지한다.
