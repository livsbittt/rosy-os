## D-163 Pinky Pro 제품 산출물은 ISO가 아니라 서명된 Raspberry Pi 디스크 이미지다

**Date:** 2026-09-22

**Status:** Accepted

**Context:** 현장 운영자는 Rosy OS 파일 하나를 확인하고 Raspberry Pi Imager로
microSD에 기록할 수 있어야 한다. 일반 PC용 Ubuntu installer ISO는 설치 프로그램을
부팅하는 매체이며 Pinky Pro의 Raspberry Pi 5 boot partition, firmware와 설치된
root filesystem을 완성된 상태로 담는 제품 산출물이 아니다. Canonical은 Raspberry Pi
용 Ubuntu Server를 `preinstalled-server-arm64+raspi.img.xz`로 배포하고, 이 이미지를
SD·USB·NVMe에 직접 기록하도록 안내한다. D-161은 Ubuntu Server 24.04 arm64와 native
ROS 2 Jazzy를 제품 기준으로 정했고, D-154는 공통 이미지와 장치별 개인화를 분리했다.

**Decision:**

1. Pinky Pro의 주 배포 산출물은
   `rosy-os-pinky-pro-<release-id>-arm64.img.xz`다. 압축을 푼 `.img`는 partition
   table, Raspberry Pi boot partition과 Ubuntu root filesystem을 포함한 raw disk
   image이며 빌드 중간 산출물이다. `.iso`는 만들거나 제품 파일로 홍보하지 않는다.
2. 이미지는 고정 SHA-256으로 검증한 Canonical Ubuntu Server 24.04 LTS
   `preinstalled-server-arm64+raspi.img.xz`에서 파생한다. 빌드는 native `aarch64`
   Ubuntu 24.04 호스트에서만 수행하며 x86 QEMU 결과를 출하하지 않는다.
3. builder는 base image를 별도 작업 사본으로 풀고 확장한 뒤 loop device로 boot/root
   partition을 mount한다. native chroot에서 고정된 Ubuntu/ROS apt 입력을 설치하고,
   검증된 ROSY offline payload, systemd units, first-boot 도구와 장치 중립 설정을
   복사한다. 원본 cache와 입력 파일은 수정하지 않는다.
4. 공통 `.img.xz`에는 hostname, `device_uid`, `ROSY_ROBOT_NUMBER`, Wi-Fi 자격,
   Fleet pairing credential 또는 SSH private key를 넣지 않는다. 이 값은 D-154의
   Windows personalizer가 SD 기록 뒤 one-shot bundle로 넣고 첫 부팅에서 Pi serial에
   결속한다.
5. 한 release는 image와 함께 `manifest.json`, `SHA256SUMS`, `SHA256SUMS.sig`,
   `sbom.spdx.json`, deb/ROS package inventory, source revision, base-image provenance와
   artifact report를 낸다. private signing key는 CI와 image builder에 두지 않고
   D-145/D-146의 검증된 unsigned handoff 뒤 승인된 offline signer만 사용한다.
6. Windows writer는 trusted public key로 `SHA256SUMS.sig`를 검증하고, 서명된
   `SHA256SUMS`의 정확한 image filename/hash가 선택한 파일과 일치할 때만
   `PlanOnly`와 write 단계로 진행한다. signature 파일의 존재만 확인하는 동작은
   MEDIA 승격에 불충분하며 이 검증이 구현되기 전에는 실제 카드를 쓰지 않는다.
7. Raspberry Pi Imager가 직접 소비하는 파일은 `.img.xz`다. 향후 다수 작업자에게
   배포할 때 Imager 2.x custom repository JSON을 추가할 수 있지만, 이는 편의용
   catalog이고 image signature, checksum, readback 또는 장치 인수를 대체하지 않는다.
8. write 성공과 전체 media readback 일치는 MEDIA 증거일 뿐이다. Pi boot, systemd,
   `ros2 pkg prefix`, 장치 ACL, motor deadman은 DEVICE에서, 서로 다른 Pinky 두 대의
   Fleet 가입·heartbeat·명령·단절 안전은 FLEET에서 별도로 판정한다.

**Alternatives:** Ubuntu live/server ISO를 배포하는 안은 Raspberry Pi 5용 완성 boot
media가 아니고 현장 설치를 대화형 단계로 되돌려 기각한다. 압축하지 않은 `.img`만
배포하는 안은 동일한 disk 내용을 불필요하게 크게 전송하므로 빌드 중간물로 제한한다.
장치별로 다른 완성 image를 만드는 안은 D-154의 공통 artifact와 서명 재사용 원칙을
깨뜨려 기각한다. Ubuntu Core image로 다시 전환하는 안은 D-161의 native Ubuntu
Server/Jazzy 운영 방식을 재설계하므로 이번 범위가 아니다.

**Consequences:** 작업자는 익숙한 “이미지 파일을 골라 SD에 굽는” 흐름을 유지하되,
실제 파일 형식과 증거는 Pi에 맞게 정확해진다. builder에는 root 권한, loop/mount,
native chroot와 cleanup 책임이 생기므로 모든 실패 경로에서 mount와 loop device를
해제해야 한다. `.img.xz` 생성만으로 출하 가능하지 않으며 offline signature와
read-only mount 검증이 끝날 때까지 ARTIFACT는 HOLD다.

**Validation / Transition:** `test_pinky_flashable_image_contract.py`가 확장자, 파일명,
Pi partition, native build, device-neutral image와 산출물 집합을 고정한다.
`test_sd_writer_contract.py`는 trusted key 기반 signature 검증이 write 전에 일어나고
signature 존재 확인만으로 진행하지 못함을 고정한다. native ARM64 builder가 실제
`.img.xz`와 evidence를 만들기 전에는 ARTIFACT, MEDIA, BOOT, DEVICE, FLEET을 GO로
쓰지 않는다.

**References:** D-145, D-146, D-154, D-161,
`docs/plans/2026-09-22-pinky-pro-flashable-image-design.md`,
`docs/plans/2026-09-22-pinky-pro-flashable-image.md`,
[Canonical Raspberry Pi installation](https://ubuntu.com/hardware/docs/boards/how-to/ubuntu_supported/raspberry-pi/),
[Canonical Ubuntu 24.04 release images](https://cdimage.ubuntu.com/ubuntu/releases/24.04/release/),
[Raspberry Pi Imager custom images](https://www.raspberrypi.com/news/how-to-add-your-own-images-to-imager/).
