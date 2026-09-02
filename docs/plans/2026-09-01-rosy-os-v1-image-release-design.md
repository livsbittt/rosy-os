# ROSY OS v1 이미지·프로비저닝·릴리스 설계

- **Status:** Approved for implementation
- **Date:** 2026-09-01
- **Target:** Raspberry Pi 5 8 GB / Raspberry Pi OS Lite 64-bit / ROS 2 Jazzy
- **Audience:** ROSY 런타임, 배포, 운영 UI, 현장 시운전 담당자
- **Related:** ROSY-CORE-SRS-001, ROSY-FLEET-SRS-001, ROSY-API-REF-001, ADR D-5/D-6/D-12/D-22/D-23/D-26 (D-26이 D-19을 대체)

## 1. 목적

ROSY OS v1을 Raspberry Pi 5에 반복 배포하고 복구할 수 있는 제품 단위로 만든다.
산출물은 공식 Raspberry Pi OS Lite를 기반으로 한 부팅 가능한 SD 이미지와, 이미
설치된 장비를 빠르게 갱신하는 서명된 Release Bundle이다.

이 문서에서 ROSY OS는 새로운 Linux 커널이나 범용 운영체제를 뜻하지 않는다.
Raspberry Pi OS 위에 ROS 2 하드웨어 어댑터, `rosy_core`, 장비 런타임, 로컬
관리 화면과 안전한 배포 계약을 결합한 **로봇용 런타임 배포판**을 뜻한다.

군중 안내, 순찰, 배송, ERP 연동과 같은 업무 기능은 ROSY OS 본체가 아니다. 이런
기능은 ROSY API와 Capability 계약을 사용하는 선택 애플리케이션 또는 Fleet
미션으로 구현한다.

## 2. 확정 결정

1. Raspberry Pi OS Lite 64-bit를 기반 OS로 사용한다.
2. 이미지 생성은 Raspberry Pi의 `rpi-image-gen` 릴리스와 커밋을 고정해 사용한다.
3. 공장 초기화와 장애 복구는 전체 SD 이미지로 수행한다.
4. 일상적인 테스트와 수정은 서명된 Release Bundle로 수행한다.
5. v1에는 전체 OS 원격 OTA와 A/B 루트 파일시스템 전환을 포함하지 않는다.
6. 이미지와 번들은 동일한 Release Manifest와 ARM64 컨테이너 digest를 사용한다.
7. 이미지에는 장비별 Wi-Fi 암호, API 토큰, SSH 개인키와 Robot ID를 넣지 않는다.
8. 운용 네트워크 모드는 `SITE_STA`와 `RELAY_AP_STA` 두 가지이며 기본은 `SITE_STA`다.
9. Wi-Fi가 설정되지 않았거나 연결 복구가 필요할 때만 임시 설정 AP를 연다. 설정 AP는
   두 운용 모드 어느 쪽으로도 프로비저닝할 수 있으며 운용 AP와 수명주기가 다르다.
10. AP+STA 릴레이는 v1 범위에 포함하되 장비별 옵트인으로 한다. 후속 Capability로
    미루지 않는다.
11. 첫 부팅, 업데이트와 자동 롤백 뒤에는 항상 `core-only`로 기동한다.
12. 모터 또는 전체 hardware 모드는 현장 점검 후 별도로 승인한다.
13. CORE는 호스트 root, Docker socket, systemd와 UART 장치를 직접 소유하지 않는다.
14. Fleet은 선택 구성요소이며 로봇 한 대의 기본 운용 조건이 아니다.

설정, manifest와 CLI에서 사용하는 runtime mode 식별자는 현재 구현과 같은
`core`, `motor`, `hardware` 세 값으로 고정한다. 이 문서의 **core-only** 또는
`CORE-ONLY` 표기는 식별자 `core`의 운영상 의미, 즉 `rosy-core`만 실행되고
`rosy-motor`와 `rosy-io`는 실행되지 않는 상태를 뜻한다.

## 3. 비범위

- 독자 Linux 커널 또는 Raspberry Pi OS 포크 유지보수
- 상시 인터넷 연결을 전제로 한 부팅
- v1 전체 OS 무중단 OTA 또는 A/B 파티션 자동 전환
- 장비 이미지에 공통 비밀번호나 공통 API 토큰 내장
- CORE 또는 Fleet의 직접 UART 쓰기
- Fleet의 지속적인 원격 `/cmd_vel` 제어
- 이미지 빌드 성공만으로 UART·모터·현장 안전 승인을 선언하는 것
- 군중 밀집도 분석, 얼굴 인식 또는 군중 안내 업무 로직

## 4. 제품 계층과 책임

```text
선택 Application
  Fleet · 안내 · 순찰 · 배송 · AI/VLA · 외부 시스템 연동
                         │ ROSY REST/WSS 계약
ROSY CORE
  Identity · Capability · State · Command Arbitration · Safety
  Navigation · Event · Diagnostics · FastAPI · Local Dashboard
                         │ 내부 ROS 2 계약
ROS 2 Hardware Adapters
  Motor · Odometry · LiDAR · IMU · ADC/Battery · LCD · LED
                         │ 제한된 /dev 접근
ROSY Device Runtime
  Boot · Network · Time · Release · Rollback · Logs · Host Agent
                         │ 최소권한 OS 계약
Raspberry Pi OS Lite 64-bit
```

### 4.1 ROSY Device Runtime

Device Runtime은 OS 이미지와 장비 생명주기를 소유한다.

- systemd 기동 순서
- NetworkManager 프로비저닝과 복구
- 장비별 신원과 자격정보 생성
- 컨테이너 이미지 import 및 Compose 기동
- Release Bundle 검증, staging, activation과 rollback
- 호스트 상태 조회와 허용된 관리 명령
- 로그 회전, 시간 동기화와 저장소 사용량 관리

### 4.2 ROSY CORE

CORE는 로봇 API와 안전한 명령 경계다. `/dev` 장치를 직접 열지 않으며 일반
호스트 관리 권한을 갖지 않는다. 현재의 Identity, Capability, State, Command,
Safety, Navigation, Event, Diagnostics, API와 Dashboard 모듈을 유지한다.

### 4.3 Hardware Adapter

어댑터는 필요한 장치만 전달받는다. `rosy-motor`는 모터 UART만, `rosy-io`는
승인된 hardware 프로파일의 장치만 받는다. 모든 이동 출력에는 드라이버 deadman과
상위 Command Manager의 watchdog이 함께 적용되어야 한다.

| runtime mode | 실행 서비스 | 장치 소유 |
|---|---|---|
| `core` | `rosy-core` | 장치 없음 |
| `motor` | `rosy-core`, `rosy-motor` | `rosy-motor`만 모터 UART |
| `hardware` | `rosy-core`, `rosy-io` | `rosy-io`만 승인된 모터·LiDAR 장치 |

`motor`와 `hardware`는 서로 다른 I/O 프로파일이며 동시에 실행하지 않는다.

### 4.4 Host Agent

Host Agent는 별도 최소권한 프로세스로 둔다. v1의 허용 명령은 명시적 allowlist를
사용하며 임의 셸을 제공하지 않는다.

- 네트워크 상태 조회와 승인된 프로파일 전환
- release 상태 조회, update 시작, rollback 요청
- 제한된 서비스 상태 조회
- 승인된 reboot 요청

업데이트 적용, reboot와 네트워크 변경은 사용자 역할, 재확인, 감사 이벤트를
요구한다. CORE 컨테이너에는 Docker socket이나 host root를 전달하지 않는다.

### 4.5 Application과 Fleet

업무 기능은 CORE 내부 모듈이 아니라 상위 소비자다. 새 기능은 다음 경계 중 하나를
사용한다.

- Capability의 additive 필드
- 등록된 원자 명령과 명확한 오류 코드
- 버전이 있는 Event와 State schema
- Fleet Mission action 또는 별도 Application API

도메인별 명칭과 상태머신을 `rosy_core`에 미리 넣지 않는다.

## 5. 파일과 영속 데이터 배치

```text
/opt/rosy/
├── releases/
│   ├── 2026.09.01-001/
│   └── 2026.09.05-002/
├── current  -> releases/2026.09.05-002
└── previous -> releases/2026.09.01-001

/etc/rosy/
├── generations/
│   └── <generation-id>/rosy.yaml
├── identity.json
├── trusted-release-keys/
│   └── <key-id>.pem
└── network/

/var/lib/rosy/
├── events/
├── maps/
├── data-generations/
│   └── <generation-id>/
├── activation.json
├── update-journal.json
├── backups/
└── release-state.json

/var/cache/rosy/releases/
└── <release-id>/
```

`releases/<release-id>`와 각 generation은 활성화 후 변경하지 않는다. 장비 신원,
신뢰 key와 network profile은 release generation 밖에 유지한다. 권위 있는 활성화
지점은 `/var/lib/rosy/activation.json` 하나이며 release 경로, config generation,
data generation과 runtime mode를 함께 기록한다. Device Runtime은 부팅할 때 이
record에서 모든 경로를 결정한다. `current`와 `previous` symlink는 운영자와 도구를
위한 파생 표시이며 부팅의 권위 있는 입력이 아니다.

새 `activation.json`은 같은 디렉터리에 쓰고 fsync한 임시 파일을 `rename`하여 한
번에 교체한다. 따라서 runtime은 이전 release/config/data 세트 또는 새 세트 중
하나만 본다. 둘이 섞인 중간 상태를 보지 않는다.

컨테이너 내부 호환 경로는 계속 `/etc/rosy/rosy.yaml`과 `/var/lib/rosy`를 사용한다.
Device Runtime이 activation record에서 선택한 host generation을 해당 컨테이너
경로에 mount하므로 CORE가 release symlink나 generation 구조를 해석하지 않는다.

## 6. Release Manifest

이미지와 번들은 다음 최소 계약을 공유한다.

```json
{
  "schema_version": 1,
  "release_id": "2026.09.01-001",
  "git_revision": "<40-hex-sha>",
  "created_at": "2026-09-01T00:00:00Z",
  "target": {
    "board": "raspberry-pi-5",
    "architecture": "arm64",
    "os_family": "raspberry-pi-os-lite",
    "os_suite": "trixie"
  },
  "runtime": {
    "config_schema": 1,
    "data_schema": 1,
    "minimum_bootloader": null
  },
  "containers": {
    "rosy_core": "sha256:<digest>",
    "rosy_io": "sha256:<digest>"
  },
  "defaults": {
    "runtime_mode": "core"
  },
  "signing_key_id": "rosy-release-2026-01",
  "requires_recommissioning": true,
  "files": [
    {"path": "images/rosy-core.oci.tar", "sha256": "<sha256>"}
  ]
}
```

`release_id`는 사람이 읽는 식별자이고 보안 판단은 Git revision, digest, 파일
checksum과 서명을 함께 사용한다. `runtime_mode`의 wire/config 값은 `core`다.
알 수 없는 manifest schema, 대상 보드 불일치, 신뢰하지 않는 signing key,
지원하지 않는 설정 또는 데이터 schema는 설치 전에 거부한다.

`containers.rosy_io`는 하나의 `rosy-io` OCI image digest다. 이 image에는
`rosy-motor` commissioning service와 `rosy-io` full-hardware service가 함께
사용하는 ROS 2 패키지가 들어 있다. `motor`와 `hardware`는 같은 signed image를
서로 다른 Compose service/장치 profile로 실행한다. 별도 `rosy-motor` OCI
artifact가 존재하는 것으로 해석하지 않는다.

## 7. 이미지 생성 파이프라인

### 7.1 도구 선택

Raspberry Pi 공식 [`rpi-image-gen`](https://github.com/raspberrypi/rpi-image-gen)을
사용한다. v1의 기준 release는 `v2.7.0`, OS suite는 Raspberry Pi OS Lite arm64
`trixie`로 잡고 WP-6 착수 시 검증한 전체 commit SHA를 lock 파일에 기록한다.
저장소에는 도구 전체를 복사하지 않고 ROSY 전용 config, layer와 hook만 관리한다.

초기 release build는 Raspberry Pi 5 8 GB의 native arm64 Raspberry Pi OS에서
수행한다. 이후 동일 lock으로 별도 ARM64 Linux runner를 추가할 수 있다.
Windows/WSL과 x86 QEMU는 개발 검증에는 사용할 수 있지만 최종 release image의
유일한 근거로 삼지 않는다. Host container runtime은 현재 배포 계약과 같은 Docker
Engine과 Compose plugin으로 고정하며 정확한 package version을 lock에 기록한다.

### 7.2 입력 고정

다음 입력은 manifest 또는 별도 lock 파일에 고정한다.

- `rpi-image-gen` tag와 commit
- Raspberry Pi OS suite와 apt source
- ROS base image digest
- Python과 ROS package lock
- Docker/Compose 또는 선택한 container runtime 버전
- `rosy_core`와 `rosy_io` image digest
- 이미지 layer와 hook의 Git revision

패키지 저장소가 갱신되어 같은 소스에서 다른 이미지가 생성될 수 있으므로 빌드
시점의 패키지 버전 목록과 repository metadata를 보존한다. v1의 재현성 목표는
**동일한 입력과 provenance를 증명하는 것**이다. bit-for-bit 동일 이미지는 별도
검증이 통과하기 전까지 주장하지 않는다.

### 7.3 이미지 포함 항목

- Raspberry Pi OS Lite 64-bit
- NetworkManager, chrony, mDNS와 필수 진단 도구
- 고정 버전 container runtime과 Compose
- 사전 빌드된 ARM64 `rosy-core`, `rosy-io` OCI archive. 후자는 `rosy-motor`와
  `rosy-io` 두 Compose service가 공유한다.
- ROSY systemd unit, first-boot와 verification scripts
- UART4 overlay 설정
- release public key
- FastAPI 대시보드 정적 자산
- 기본 `core-only` runtime 설정

이미지 build 중 OCI archive를 설치하고 첫 부팅에서 로컬 import한다. 최초 CORE
기동과 대시보드 표시에 인터넷이 필요해서는 안 된다.

### 7.4 산출물

```text
rosy-pi5-<release-id>.img.xz
rosy-pi5-<release-id>.bmap
manifest.json
SHA256SUMS
SHA256SUMS.sig
sbom.spdx.json
release-notes.md
```

배포 디렉터리의 `SHA256SUMS`는 압축 이미지, bmap, manifest, SBOM과 release notes를
경로 오름차순으로 열거한다. `SHA256SUMS.sig`는 이 파일의 **정확한 바이트**에 대한
Ed25519 detached signature다. 사용자는 checksum 목록의 서명을 먼저 검증한 뒤
각 파일 checksum을 확인하고 Raspberry Pi Imager의 Custom Image 또는 검증된
CLI로 SD에 기록한다. 압축 이미지 자체의 metadata가 달라도 서명된 checksum과
일치하지 않으면 배포하지 않는다.

## 8. 첫 부팅과 Wi-Fi 프로비저닝

### 8.1 네트워크 모드

```text
UNPROVISIONED
  -> PROVISIONING_AP
  -> VERIFYING_SITE_WIFI
       -> SITE_STA          (network.mode = site_sta, 기본)
       -> RELAY_AP_STA      (network.mode = relay, 장비별 옵트인)
       -> PROVISIONING_AP

SITE_STA / RELAY_AP_STA 업링크 연결 실패
  -> NETWORK_HOLD

명시적 one-shot recovery 요청 + 재부팅
  -> RECOVERY_AP
  -> VERIFYING_SITE_WIFI
```

운용 모드는 두 가지이고 기본은 `SITE_STA`다. 이 모드에서 작업자 단말, Site Fleet와
1~10대 로봇은 하나의 사업장 공유기 또는 모바일 라우터 WLAN에 접속한다. 인터넷은
선택 사항이며 같은 WLAN 안의 로컬 API와 대시보드는 인터넷 단절에도 유지한다.

`RELAY_AP_STA`는 장비별 설정(`network.mode = relay`)으로 켜는 옵트인 모드다. 로봇이
상위 WiFi에 STA로 붙은 채 동시에 자체 AP를 열어 릴레이하고, 사용자 단말은 로봇 AP를
통해 접속한다. 상위 공유기가 없거나 신뢰할 수 없는 현장과 시운전에 쓴다. 단일 라디오
제약(AP는 상위와 동일 채널)과 다수 로봇 동시 운용 시의 간섭은 이 모드를 켠 장비에
국한되며 접속 가이드에 명시한다. 릴레이 업링크가 끊겨도 로봇 AP 서브넷 안의 로컬
제어는 유지한다.

`PROVISIONING_AP`와 `RECOVERY_AP`는 설정을 위한 임시 모드이며 `RELAY_AP_STA`의 운용
AP와 별개 프로파일이다. 설정 AP의 자격정보를 운용 AP가 재사용하지 않는다. 두 운용
모드 어느 쪽으로 갈지는 프로비저닝 단계에서 선택하고 장비별 설정에 기록한다.

이 결정은 ADR D-26이며 D-19을 대체한다. SRS NET-001~005가 함께 개정되었다.

프로비저닝 AP는 첫 부팅에만 자동으로 열린다. 이미 provisioned인 장비에서는 짧은
WLAN 단절만으로 recovery AP를 열지 않는다. v1 recovery AP는 다음 중 하나로만
요청한다.

- 정상 로컬 대시보드에서 관리자가 다음 재부팅의 recovery mode를 예약
- 전원이 꺼진 장비의 FAT boot partition에 빈 `rosy-recovery` marker를 기록

연결 실패 자체는 `NETWORK_HOLD`이며 recovery AP를 자동으로 열지 않는다. 부팅
초기에 Device Runtime은 dashboard 예약 또는 boot marker를 boot ID가 포함된 내부
one-shot request로 원자 이동한 뒤 원본 요청을 삭제한다. 같은 요청은 다음 부팅에
다시 적용되지 않는다. AP 시작이 실패해도 one-shot은 소비되고, 실패 이유를 로컬
LCD와 release/network 상태에 기록한다. 작업자는 필요하면 새 요청을 만든다.

Device Runtime은 recovery boot에서 `core` mode를 강제하고 `rosy-motor`와
`rosy-io`가 정지했음을 확인한 뒤에만 AP를 연다. AP는 장비별 무작위 16자 이상의
WPA2 PSK를 사용한다. 최초 setup PSK는 로컬 LCD에 제한 시간 동안 표시하고 로그와
API에 기록하지 않는다. LCD가 없거나 고장 난 장비는 flash-time provisioning을
사용한다. setup endpoint는 AP interface에서만 listen하고 20분 동안 활동이 없으면
AP를 닫는다. 활성 세션이 있으면 만료를 연장할 수 있다.

### 8.2 첫 부팅 흐름

1. Device Runtime은 유효한 장비 신원과 NetworkManager site profile을 확인한다.
2. 없으면 `ROSY-SETUP-<short-id>` AP를 열고 `10.42.0.1`에서 setup UI를 제공한다.
3. 사용자는 국가 코드, Site Wi-Fi, Robot ID와 hostname을 입력한다.
4. Wi-Fi secret은 로그, 이벤트, API 응답과 영구 browser storage에 기록하지 않는다.
5. 임시 후보 profile로 site 연결, IPv4, 기본 route와 선택적 인터넷을 검사한다.
6. 같은 WLAN에서 대시보드 접근이 가능한지 별도 확인 대상으로 표시한다.
7. 성공하면 후보를 확정하고 setup AP와 setup endpoint를 비활성화한다.
8. 실패하면 후보를 폐기하고 AP로 돌아가 구체적인 실패 이유를 표시한다.
9. 장비별 API token과 device key는 Pi에서 생성한다.
10. 모든 과정에서 runtime mode는 `core`이며 `rosy-motor`와 `rosy-io`를 시작하지 않는다.

대량 설치에서는 Raspberry Pi Imager 또는 별도 flasher가 장비별 설정을 주입하는
경로를 추가할 수 있다. 이 경로도 재사용 이미지에 비밀값을 포함해서는 안 된다.

### 8.3 접속 주소

- 우선: `http://rosy-NN.local:8080/dashboard`
- 폴백: NetworkManager 또는 공유기에서 확인한 `wlan0` IPv4
- 설정/복구 AP: `http://10.42.0.1/setup`

인터넷 성공과 WLAN peer 접속 성공은 서로 다른 gate로 판정한다. 공유기의 client
isolation으로 peer 접속만 실패할 수 있다.

## 9. Release Bundle과 업데이트

### 9.1 Bundle 내용

- Release Manifest와 detached signature
- ARM64 OCI image archive
- Compose, systemd와 runtime scripts
- additive 설정 schema migration
- 필요한 데이터 migration과 rollback metadata
- release notes와 운영 주의사항

Bundle 파일 형식은 `rosy-release-<release-id>.tar.zst`로 고정한다. archive 내부의
`SHA256SUMS`는 `manifest.json`과 모든 payload 파일을 경로 오름차순으로 열거하며
`SHA256SUMS.sig`는 그 정확한 바이트에 대한 Ed25519 detached signature다. 서명은
OpenSSL 3이 처리할 수 있는 raw Ed25519 signature를 base64로 저장한다. updater는
archive member를 풀기 전에 전체 목록을 읽고 절대경로, `..`, symlink/hardlink,
중복 경로와 허용되지 않은 파일 형식을 거부한다. 검증된 파일만 소유자 전용 임시
staging directory에 푼다.

릴리스 signing private key는 저장소, 이미지와 일반 build host에 두지 않고 별도
서명 환경에서만 사용한다. 장비는 `/etc/rosy/trusted-release-keys/<key-id>.pem`의
public key로 `signing_key_id`를 검증한다. v1은 단일 신뢰 key를 사용하며 key 교체와
폐기는 새 recovery image로만 수행한다. 온라인 key rotation은 v1 비범위다.

### 9.2 업데이트 상태머신

```text
RECEIVED
  -> SIGNATURE_VERIFIED
  -> CHECKSUM_VERIFIED
  -> COMPATIBILITY_CHECKED
  -> STAGED
  -> CONFIG_BACKED_UP
  -> MIGRATION_VALIDATED
  -> ACTIVATING_CORE_ONLY
  -> CORE_HEALTHY
  -> ACTIVATED_CORE_ONLY
       -> COMMISSIONING_REQUIRED
  -> ROLLING_BACK
  -> ROLLED_BACK_CORE_ONLY
```

각 상태와 실패 이유를 `/var/lib/rosy/release-state.json`과 감사 이벤트에 기록한다.
전원 재인가 후에도 updater는 마지막 완료 상태를 읽어 미완료 staging을 정리하거나
안전한 이전 버전으로 복구해야 한다.

### 9.3 활성화 절차

1. 안전한 member 목록을 검사한 뒤 임시 staging에 풀며, payload 사용 전에 checksum과
   서명을 검증한다.
2. board, architecture, runtime과 schema 호환성을 검사한다.
3. 새 불변 release directory에 파일을 staging한다.
4. `/etc/rosy`와 필요한 데이터의 제한된 backup을 만든다.
5. migration을 backup의 작업 사본에 실행하고 schema와 결과를 검증한다. 이 단계는
   live config/data와 release pointer를 변경하지 않는다.
6. OCI archive를 import하고 manifest digest와 실제 image digest를 대조한다.
7. migration 결과를 새 immutable config/data generation으로 설치한다.
8. journal에 old activation record, candidate activation record, old pointer와 backup
   경로를 fsync해 기록한다.
9. 기존 runtime을 정지하고 candidate `activation.json`을 원자 반영한다.
10. 표시용 `current`를 candidate로 갱신하고 candidate activation record의 경로로
    새 release를 `core`로 시작한다.
11. 최대 90초의 bounded health check를 수행한다.
12. 성공하면 `previous=old release`를 갱신하고 journal을 완료 처리한다.
13. 실패하면 candidate를 정지하고 old activation record를 원자 복원한 뒤 표시용
    pointer와 backup을 정리하고 이전 release를 `core`로 시작한다.
14. 업데이트와 rollback 어느 쪽도 `motor` 또는 `hardware`를 자동 복구하지 않는다.

`rosy-release-recover.service`는 모든 boot에서 `rosy-runtime.service`보다 먼저
실행되는 oneshot unit이다. runtime unit은 이를 `Requires=`와 `After=`로 의존한다.
recover unit은 미완료 journal이 없음을 확인하거나 13번 rollback과 이전 CORE
health 확인을 끝내기 전까지 runtime 기동을 허용하지 않는다. rollback CORE도
실패하면 runtime을 비활성화하고 boot는 `RECOVERY HOLD`로 남긴다. 따라서 전원
손실 뒤 old release가 new generation을 읽거나 candidate가 복구 전에 시작하지
않는다.

### 9.4 마이그레이션 규칙

- v1은 additive 또는 backward-compatible migration만 허용한다.
- migration은 재실행 가능하고 완료 marker를 남겨야 한다.
- migration은 backup 생성 뒤 작업 사본에 실행하며 성공 검증 전 live data를
  변경하지 않는다.
- migration 결과는 새 immutable generation에 설치하고 candidate activation
  record가 선택되기 전까지 runtime에 노출하지 않는다.
- rollback 후 이전 릴리스가 읽지 못하는 데이터 변경은 금지한다.
- 장비 신원, release public key와 사용자 설정은 release 파일로 덮어쓰지 않는다.
- backup 범위, 크기 제한, 보존 수와 복구 결과를 대시보드에 표시한다.

## 10. Dashboard 운영 화면

현재 구현된 FastAPI 내장 대시보드를 유지하고 별도 Node 런타임을 추가하지 않는다.
아래 Network, Release와 Host Agent 동작은 아직 구현되지 않은 확장 범위다.

### 10.1 장비

- Robot ID, hostname, 모델, architecture와 OS 버전
- CORE, I/O, ROS graph와 장치 상태
- CPU, memory, disk, temperature와 network
- runtime mode와 commissioning 상태

### 10.2 네트워크

- 현재 모드: PROVISIONING_AP / SITE_STA / RELAY_AP_STA / RECOVERY_AP / NETWORK_HOLD
- SSID는 표시할 수 있으나 password와 secret은 절대 표시하지 않는다.
- WLAN IPv4, default route, DNS와 Internet 상태
- peer dashboard 접근을 위한 주소와 client-isolation 안내

### 10.3 릴리스

- current, previous, staged release ID
- Git revision, image digest, config/data schema
- signature/checksum/compatibility/health 결과
- 마지막 업데이트와 실패 원인
- rollback 가능 여부
- `COMMISSIONING_REQUIRED`와 hardware 재승인 사유

Host Agent 명령은 API의 역할 검사, 사용자 확인, idempotency key와 감사 로그를
거친다. Viewer는 조회, Administrator는 업데이트와 rollback 요청이 가능하다.
E-stop 해제나 hardware mode 승격은 별도 현장 안전 절차를 따른다.

## 11. 실패 처리 매트릭스

| 실패 | 자동 동작 | 운영 상태 |
|---|---|---|
| 이미지 checksum/서명 불일치 | 기록 중단 | BUILD/FLASH HOLD |
| 첫 부팅에 Wi-Fi 설정 없음 | 설정 AP 시작 | PROVISIONING |
| Site Wi-Fi 인증 실패 | 후보 폐기, 설정 AP 복귀 | NETWORK HOLD |
| Wi-Fi 연결, 인터넷 없음 | 로컬 운용 유지 | INTERNET WARN |
| 인터넷 성공, peer dashboard 실패 | client isolation 안내 | NETWORK HOLD |
| Bundle 서명/파일 checksum 실패 | bundle 격리, current 유지 | UPDATE REJECTED |
| Board/architecture/schema 불일치 | 설치 거부 | UPDATE REJECTED |
| OCI digest 불일치 | staging 폐기 | UPDATE REJECTED |
| 새 CORE health 실패 | journal의 old_current로 rollback | CORE-ONLY HOLD |
| 업데이트 중 전원 손실 | journal 상태로 재개/정리 | CORE-ONLY HOLD |
| rollback CORE도 실패 | runtime 비활성화, 복구 안내 | RECOVERY HOLD |
| UART 또는 모터 검증 전 | motor/I/O 시작 금지 | MOTOR HOLD |

실패 메시지는 집계 숫자만 표시하지 않고 실패 단계, 대상 release, 오류 코드와
복구 행동을 제공한다. 로그에는 token, Wi-Fi password, private key와 전체 설정
파일을 기록하지 않는다.

## 12. 검증과 증거 등급

### 12.1 자동 검증

- manifest schema, required field와 path traversal 거부
- release ID, Git SHA와 digest 형식
- 모든 bundle 파일 checksum과 signature 검증
- secret fixture가 image/artifact에 포함되지 않는지 검사
- ARM64 container architecture와 immutable digest 검사
- Compose에서 CORE의 device/Docker socket/host root 접근 금지
- 기본 `ROSY_RUNTIME_MODE=core`
- 손상, 미서명, downgrade와 비호환 bundle 거부
- update/rollback 후 hardware 자동 시작 금지
- first-boot 완료 후 setup endpoint 비활성화
- recovery AP가 명시적 요청과 `core` mode에서만 활성화
- NetworkManager 후보 profile 실패 시 기존 profile 보존
- shell `bash -n`, PowerShell AST, YAML/JSON schema와 `git diff --check`

### 12.2 이미지 검사

- 파티션과 filesystem 생성
- 필수 systemd unit enablement와 dependency 순서
- public key, manifest와 OCI archive 존재
- 공통 비밀번호, API token, Wi-Fi secret와 SSH private key 부재
- UART overlay 존재하되 motor service는 비활성
- 이미지 압축 해제와 checksum 재검증

### 12.3 Raspberry Pi 5 인수

1. SD 기록 후 유선 연결 없이 부팅한다.
2. 설정 AP와 setup UI로 Site Wi-Fi와 운용 모드를 등록한다.
3. 실패한 자격정보에서 AP 복귀를 확인한다.
4. `SITE_STA`에서 mDNS와 IPv4 대시보드에 다른 단말로 접속한다.
5. 인터넷과 peer 접속을 각각 기록한다. 공유기의 client isolation으로 peer만
   실패할 수 있으므로 같은 판정으로 묶지 않는다.
5a. `RELAY_AP_STA`를 켠 장비에서 사용자 단말이 로봇 AP를 경유해 접속되는지,
    상위 업링크를 끊어도 로봇 AP 서브넷 안의 제어가 유지되는지 확인한다.
6. 인터넷을 차단해도 로컬 대시보드가 유지되는지 확인한다.
7. 전원 재인가 후 CORE 자동 복구를 확인한다.
8. 정상 update, 손상/미서명 update와 health-failure rollback을 실행한다.
9. 모든 update/rollback 후 motor/I/O가 꺼져 있는지 확인한다.
10. UART·모터·열·저장소 로그 증가는 별도 commissioning으로 승인한다.

### 12.4 판정

| Gate | 의미 |
|---|---|
| `BUILD_GO` | 이미지와 부속 산출물이 생성되고 자동 검증 통과 |
| `BOOT_GO` | 실제 Pi 5가 해당 이미지로 부팅 |
| `NETWORK_GO` | Wi-Fi 설정, 복구와 다른 단말 접속 통과 |
| `UPDATE_GO` | 정상 update와 실패 rollback 실기 통과 |
| `MOTOR_HOLD` | UART·모터 승인 전의 정상 상태 |
| `FIELD_GO` | 요청된 하드웨어와 현장 안전시험까지 완료 |

`BUILD_GO`는 `BOOT_GO`를 대신하지 않으며 컨테이너 health는 `MOTOR_HOLD`를
해제하지 않는다. 실기 증거가 없는 gate는 완료로 표시하지 않는다.

## 13. 구현 작업 패키지

아래 순서는 안전 경계를 먼저 고정하고 그 위에 기능을 쌓는다.

### WP-1 Release 계약

- `deploy/release/manifest.schema.json`
- manifest 생성기와 validator
- checksum/signature 생성 및 검증
- path traversal, 중복 파일, 대상 불일치 테스트

**완료 조건:** 유효한 fixture는 통과하고 손상·미서명·비호환 fixture는 이유와 함께
거부된다.

### WP-2 불변 Release Layout과 updater

- versioned release staging
- `current`/`previous` 원자 전환
- persistent config/data 분리
- update journal과 전원 손실 복구
- CORE health 실패 rollback

**완료 조건:** 성공 update와 의도적 실패 rollback 뒤 모두 `core-only`이며 이전
릴리스와 설정이 보존된다.

### WP-3 Network Provisioner

- AP-only setup/recovery NetworkManager profile
- 일회성 setup API/UI
- candidate Site Wi-Fi 검증과 commit/rollback
- provisioning 완료 후 endpoint와 AP 비활성화
- Internet과 peer-access 결과 분리

**완료 조건:** 잘못된 Wi-Fi에서 setup AP로 돌아오고 정상 Wi-Fi에서는 SITE_STA로
전환한다. 어떤 응답과 로그에도 password가 없다.

### WP-4 최소권한 Host Agent

- typed request/response 계약
- network/release/status/reboot allowlist
- 역할, 재확인, idempotency와 audit
- 임의 명령, 임의 경로와 Docker socket 접근 거부

**완료 조건:** 허용된 명령만 수행하고 CORE가 호스트 관리 권한을 얻지 않는다.

### WP-5 Dashboard 확장

- Network, Release, Commissioning 상태 카드
- 현재/이전 릴리스와 실패 이유
- setup과 recovery 안내
- 업데이트/rollback의 확인, 중복 요청 잠금과 per-step 결과

**완료 조건:** 사용자가 실패 원인과 다음 행동을 알 수 있으며 secret이 노출되지
않는다.

### WP-6 `rpi-image-gen` 통합

- tool version lock
- Raspberry Pi OS `trixie` arm64와 Docker/Compose package version lock
- ROSY config/layer/hook
- ARM64 OCI archive 포함
- manifest, signature, SBOM, checksum과 compressed image 출력
- release artifact 보존 정책

**완료 조건:** native ARM64 runner에서 SD 기록 가능한 이미지와 모든 부속 산출물이
생성된다.

최소 보존 정책은 마지막 정상 release 3개와 현장에 설치된 모든 current/previous
release, 그리고 최초 factory recovery image다. signing private key와 서명 작업
로그는 일반 artifact와 분리 보관한다.

### WP-7 실기 인수

- Pi 5 8 GB 이미지 부팅
- 무유선 Wi-Fi provisioning과 peer dashboard
- offline local operation
- 정상 update, 거부와 rollback
- 재부팅·전원 손실 복구
- 별도 UART·모터 commissioning

**완료 조건:** 각 gate의 실제 장비 증거가 기록되고 충족되지 않은 gate는 HOLD로
남는다.

## 14. 목표 명령 인터페이스

다음은 구현 후 제공할 목표 인터페이스이며 현재 존재한다고 가정해서는 안 된다.

```bash
# Native ARM64 build host
./deploy/image/build-image.sh --release-id 2026.09.01-001
./deploy/image/verify-artifacts.sh dist/2026.09.01-001

# Installed robot
sudo rosy-release verify rosy-release-2026.09.05-002.tar
sudo rosy-release install rosy-release-2026.09.05-002.tar
sudo rosy-release status
sudo rosy-release rollback

# Runtime remains core-only until separately commissioned
sudo /opt/rosy/current/deploy/robot/runtime-mode.sh status
```

CLI는 machine-readable JSON 출력 옵션을 제공해야 하며 성공/실패를 exit code로
구분한다. 대시보드는 셸을 호출하지 않고 Host Agent의 typed API를 사용한다.

## 15. 구현 시 반드시 함께 개정할 문서

- `docs/reference/ROSY ADR Log.md`: D-19를 D-26으로 대체 (SITE_STA 기본 + 릴레이 옵트인)
- `docs/spec/ROSY CORE SRS.md`: NET-001~005와 Host Agent/Release 책임 경계
- `docs/reference/ROSY API & Protocol Reference.md`: network/release typed contract
- `docs/deployment/raspberry-pi-wifi-image.md`: custom ROSY image와 setup AP 절차
- `docs/deployment/raspberry-pi-runtime.md`: versioned release layout과 rollback

이 문서 개정은 구현과 같은 변경 집합에서 계약 테스트와 함께 수행한다. 현재 승인된
문구와 구현이 충돌할 때 조용히 한쪽만 변경하지 않는다.

## 16. 완료 정의

ROSY OS v1 이미지 작업은 다음 조건을 모두 만족할 때 완료다.

- 고정된 입력에서 release image와 manifest/signature/SBOM/checksum 생성
- 이미지에 장비별 secret이 없음
- 첫 부팅 setup AP에서 선택한 운용 모드(`SITE_STA` 또는 `RELAY_AP_STA`)로 안전하게 전환
- 인터넷 없이 CORE와 대시보드 기동
- 다른 WLAN 단말에서 상태 확인
- 정상 Release Bundle update와 실패 rollback
- update와 rollback 후 `core-only`
- current/previous release와 실패 원인이 대시보드에 표시
- 실제 Pi 5의 BUILD/BOOT/NETWORK/UPDATE gate 증거 기록
- UART·모터 미승인 상태는 정직하게 `MOTOR_HOLD`로 유지

릴레이 모드를 켠 장비에서는 사용자 단말이 로봇 AP를 경유해 대시보드에 접속하고,
업링크가 끊겨도 로봇 AP 서브넷 안의 로컬 제어가 유지됨을 함께 확인한다.

전체 OS A/B OTA와 도메인별 응용 기능은 이 완료 정의에 포함하지 않는다.
