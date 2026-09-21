# ROSY SD 카드 개인화 설계

- 작성일: 2026-09-21
- 상태: 구현 승인
- 관련 결정: D-15, D-22, D-26, D-33, D-36, D-66, D-154
- 결정 근거: D-154 Accepted

## 1. 목표

하나의 검증된 Rosy OS 기본 이미지를 여러 Pinky Pro에 공통으로 기록한 뒤,
Windows 운영자 스크립트가 선택한 SD 카드에 장치별 신원과 Wi-Fi 설정을 안전하게
개인화한다. 사용자가 보는 장치명은 `rosy-pinky-<4자리>`이고, ROS/DDS 내부 신원과
전역 고유 ID는 별도 필드로 유지한다.

이 설계는 이미지 생성, 카드 개인화, 첫 부팅 적용, 장치 readback을 서로 다른
증거 단계로 취급한다. 스크립트가 파일을 만들었다는 사실은 Pi 부팅이나 Pinky Pro
동작을 증명하지 않는다.

## 2. 확정 결정

1. 기본 이미지는 모든 Pinky Pro에 동일하며 Robot ID, 현장 Wi-Fi 비밀정보, API
   token, SSH private key를 포함하지 않는다.
2. 사람이 보는 장치명과 hostname은 `rosy-pinky-<4자리>` 형식이다.
3. 네 글자는 소문자 영숫자에서 혼동 문자인 `0`, `o`, `1`, `i`, `l`을 제외한
   31자 alphabet으로 암호학적 난수를 생성한다. 예: `rosy-pinky-k7m4`.
4. 네 글자 이름은 편의 식별자일 뿐이다. 전역 신원은 별도 UUIDv4 `device_uid`이고,
   첫 부팅에서 Raspberry Pi hardware serial과 결속한다.
5. v1의 DDS 계약은 유지한다. `ROSY_ROBOT_NUMBER=N`, `ROS_DOMAIN_ID=40+N`,
   `ROSY_NAMESPACE=rosy_NN`은 내부 통신용이며 hostname에 노출하지 않는다.
6. `ROSY_ROBOT_NUMBER`에는 기본값을 두지 않는다. SD 개인화 때 운영자가 명시하고
   기존 장치 등록부와 중복을 검사한다.
7. 첫 부팅 runtime은 항상 `core`이다. 요청한 `motor`/`hardware` preset은 의도로만
   기록하며 G3/G4/G5 승격 전에 자동 활성화하지 않는다.
8. Wi-Fi는 카드 개인화 때 자동 주입한다. 비밀번호 평문은 명령행, 로그, Git,
   이미지에 남기지 않는다.

## 3. 신원 모델

```yaml
schema_version: 1
device_uid: "550e8400-e29b-41d4-a716-446655440000"
device_name: rosy-pinky-k7m4
hostname: rosy-pinky-k7m4
platform: rosy
model_family: pinky
model: pinky_pro
hardware_serial: null
short_code: k7m4
ros_identity:
  robot_number: 1
  domain_id: 41
  namespace: rosy_01
requested_preset: hardware
```

`device_uid`와 `device_name`은 카드 개인화 시 생성하고 이후 불변이다. `hostname`과
`device_name`은 v1에서는 동일하다. 사용자용 `display_name`은 Fleet가 생긴 뒤
변경 가능한 별도 속성으로 추가하며 장치 신원을 바꾸지 않는다.

첫 부팅은 `/proc/device-tree/serial-number`를 읽어 `hardware_serial`을 채운다. 이미
다른 serial에 결속된 `device_uid`를 재사용하거나, 같은 등록부에서 장치명·로봇
번호가 중복되면 설치를 거부한다. SD 또는 Pi 교체는 자동 동일시하지 않고 명시적인
재결속 절차를 요구한다.

## 4. Wi-Fi 비밀정보 처리

운영자 PC는 현장 SSID와 비밀번호를 저장소 밖의 DPAPI 보호 파일에 보관한다.
`prepare-rosy-sd.ps1`은 현재 Windows 사용자만 복호화할 수 있는 credential을 읽고,
PBKDF2-HMAC-SHA1 4096회로 32-byte WPA PSK를 파생한다. 카드에는 평문 passphrase가
아니라 64자리 hex PSK만 기록한다. 이 값도 네트워크 접속 비밀이므로 로그와 readback에
절대 포함하지 않는다.

개인화 bundle은 boot 파티션의 일회성 경로에 놓는다. 첫 부팅 서비스는 schema,
release ID, 모델, 신원 범위와 checksum을 검증한 다음 NetworkManager profile을
`/etc/NetworkManager/system-connections/rosy-site-sta.nmconnection`에 mode `0600`으로
설치한다. 성공 후 boot 파티션의 bundle을 삭제하고 소비 marker만 남긴다.

비밀번호가 짧으면 원래 passphrase가 없어도 raw PSK에 대한 오프라인 추측 공격이
가능하다. 따라서 이 방식은 평문 노출을 줄이지만 약한 현장 비밀번호를 강하게 만들지는
않는다.

## 5. Windows SD 개인화 흐름

운영자는 관리자 PowerShell에서 다음 형태로 실행한다. 비밀번호는 인자로 넘기지 않는다.

```powershell
.\deploy\sd\prepare-rosy-sd.ps1 `
  -DiskNumber 1 `
  -RobotNumber 1 `
  -Model pinky_pro `
  -Preset hardware `
  -WifiProfile site-default `
  -ImagePath .\dist\rosy-os-<release>.img.zst
```

스크립트는 다음 순서를 바꾸지 않는다.

1. 관리자 권한, `rpi-imager` version, 이미지 파일, signed checksum을 확인한다.
2. `Get-Disk`로 대상의 number, bus type, model, serial, size, boot/system 여부를 다시
   읽는다.
3. USB/removable이 아니거나 boot/system disk이거나 허용 용량 밖이면 거부한다.
4. UUID, 짧은 코드와 장치명을 생성하고 로컬 등록부 중복을 검사한다.
5. redacted 계획을 출력하고 사용자가
   `ERASE DISK <n> <device_name>`을 정확히 입력해야 진행한다.
6. 공식 `rpi-imager --cli --sha256`로 이미지를 기록하며 write verification을 끄지
   않는다.
7. 새 boot 파티션을 다시 발견해 일회성 개인화 bundle을 원자적으로 기록한다.
8. bundle을 다시 읽어 checksum과 redaction을 검사하고 카드/이미지/신원 receipt를
   저장한다.

`-PlanOnly`는 1~5단계의 비파괴 결과만 출력한다. 테스트와 첫 현장 확인은 반드시
`-PlanOnly`부터 수행한다.

## 6. 첫 부팅 상태 전이

```text
factory image
  -> bundle 검증
     -> 실패: runtime 정지 + PROVISIONING_AP
     -> 성공: identity/hostname 후보 기록
        -> Wi-Fi 후보 활성화
           -> 실패: 후보 폐기 + PROVISIONING_AP
           -> 성공: SITE_STA commit + bundle 삭제
              -> core-only runtime
                 -> G1/G2 readback
```

처음부터 성공한 적 없는 장치는 자동 bundle 실패 후 `PROVISIONING_AP`로 돌아갈 수
있다. 이미 provisioned인 장치의 평범한 WLAN 장애는 자동 AP를 열지 않고 기존
D-26 계약대로 `NETWORK_HOLD`에 머문다. 어떤 실패도 motor/hardware preset을
활성화하지 않는다.

첫 부팅 기록은 SSID, device name, release ID, 결과 code만 포함한다. PSK,
passphrase, API token과 전체 NetworkManager profile은 감사 로그에 넣지 않는다.

## 7. 코드 배치

- `deploy/sd/personalization.py`: 이름, UUID, manifest, WPA PSK 파생과 검증
- `deploy/sd/prepare-rosy-sd.ps1`: Windows disk preflight, 확인, flash, bundle 기록
- `deploy/sd/provision.schema.json`: 일회성 bundle JSON schema
- `deploy/robot/apply-sd-provision.py`: Pi 첫 부팅 소비자
- `deploy/robot/rosy-sd-provision.service`: network/runtime보다 먼저 실행하는 unit
- `deploy/robot/config/board.yaml`: Pinky 계열 identity prefix 선언
- `deploy/image/`: 공통 이미지에 소비자와 unit만 포함하는 rpi-image-gen layer
- `test/test_sd_personalization.py`: ROS-free 생성/검증/비밀정보 계약
- `test/test_sd_writer_contract.py`: Windows 비파괴/파괴 경계 계약
- `test/test_first_boot_provisioning.py`: Pi root fixture와 상태 전이 계약

## 8. 실패와 복구

- 이미지 hash/signature 불일치: 카드에 쓰기 전에 종료한다.
- 대상 disk drift: 확인 직전과 기록 직전에 다시 읽고 하나라도 달라지면 종료한다.
- 기존 receipt와 identity 충돌: 자동 덮어쓰기하지 않는다.
- flash 실패: 개인화하지 않고 실패 receipt만 남긴다.
- bundle 기록 실패: 카드를 배포 가능으로 표시하지 않는다.
- first-boot schema/checksum 실패: bundle을 적용하지 않고 `PROVISIONING_AP`로 간다.
- Wi-Fi association/IP 실패: 후보 profile을 제거하고 평문 비밀정보 없이 원인 code를
  남긴다.
- 장치 readback 불일치: runtime을 `core`에 두고 G2를 HOLD한다.

## 9. 검증 단계

1. **SOURCE:** Python/PowerShell 계약 테스트와 secret scan.
2. **ARTIFACT:** native ARM64에서 공통 이미지, manifest, signature, checksum 생성.
3. **MEDIA:** `rpi-imager` write verification과 카드에서 다시 읽은 receipt 일치.
4. **BOOT:** Pi 5 부팅, hostname, serial binding, `SITE_STA`, core health.
5. **DEVICE:** G0~G5 commissioning과 물리 Pinky Pro 검증.

현재 연결된 SD를 인식했다는 사실은 MEDIA가 아니다. 실제 이미지 기록은 SOURCE와
ARTIFACT가 통과하고 운영자가 최종 erase 문구를 입력한 뒤에만 수행한다.

## 10. 비범위

- 랜덤 ROS namespace 또는 랜덤 ROS domain
- Wi-Fi 비밀번호나 release signing private key의 Git 저장
- 첫 부팅에서 motor/hardware 자동 활성화
- SD 복제만으로 기존 장치 identity 이전
- Windows/x86 결과를 ARM64 이미지 또는 Pinky Pro 실기 합격으로 간주

## 11. 도구 근거

- Raspberry Pi `rpi-image-gen`: 공통 이미지 생성과 외부 config/layer 통합
- Raspberry Pi Imager CLI: `--cli --sha256 <hash> <image> <device>` 기록과 검증
