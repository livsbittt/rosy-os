# Raspberry Pi 5 실기 인수 체크리스트 (WP-6 / WP-7)

- **Document ID:** ROSY-DEPLOY-ACCEPT-001
- **Status:** 인계 문서 — 아래 게이트는 **아직 하나도 통과하지 않았다**
- **Related:** `docs/plans/2026-09-01-rosy-os-v1-image-release-design.md` §12,
  `docs/deployment/release-signing-key.md`, `docs/deployment/release-retention.md`

## 0. 이 문서의 위치

WP-1(릴리스 계약)과 WP-2(불변 layout·updater)는 하드웨어 없이 구현·검증했다.
`BUILD_GO`부터는 실제 Pi 5, SD 카드, 서명 환경이 필요하다. 이 문서는 그 지점에서
사람이 이어받기 위한 것이다.

**현재 게이트 상태 — 어느 것도 통과로 표시하지 않았다:**

| Gate | 상태 | 막고 있는 것 |
|---|---|---|
| `BUILD_GO` | **HOLD** | native ARM64 빌드 호스트에서 이미지를 만든 적 없음 |
| `BOOT_GO` | **HOLD** | 실제 Pi 5가 그 이미지로 부팅한 적 없음 |
| `NETWORK_GO` | **HOLD** | 실기 Wi-Fi 프로비저닝·복구·peer 접속 미검증 |
| `UPDATE_GO` | **HOLD** | 실기 update/rollback 미검증 (tmpdir 검증만 완료) |
| `MOTOR_HOLD` | **정상 상태** | UART·모터 미승인. 유지되어야 한다 |
| `FIELD_GO` | **HOLD** | 위 전부의 후행 |

컨테이너 health가 초록이어도 `MOTOR_HOLD`는 풀리지 않는다. `BUILD_GO`는
`BOOT_GO`를 대신하지 않는다.

## 1. 준비물

- **Raspberry Pi 5 8 GB** — 인수 대상 장비
- **native ARM64 빌드 호스트** — Raspberry Pi OS arm64가 도는 Pi 5.
  인수 대상과 같은 장비를 써도 되지만, 이미지를 구우면 그 장비의 OS가 지워지므로
  **별도 장비 1대를 권장**한다. x86 QEMU 빌드는 개발 검증용이며 최종 릴리스
  이미지의 근거로 삼지 않는다(설계 §7.1).
- **SD 카드 32 GB 이상 2장** — 최소 용량 근거는 `release-retention.md` §2.
  1장은 굽기 대상, 1장은 롤백 실패 시 복구용.
- **서명 환경** — `release-signing-key.md` §3~5. 개인키를 빌드 호스트에 두지 않는다.
- **사업장 Wi-Fi 자격정보** — SSID, PSK, 국가 코드
- **두 번째 단말** — peer 접속 확인용 (노트북 또는 휴대폰)
- **모니터·키보드** 또는 **UART 콘솔** — 부팅 실패 시 화면을 봐야 한다

## 2. WP-6 착수 전에 검증할 미확인 가정

아래 셋은 설계가 전제하지만 **아직 아무도 확인하지 않았다.** 빌드 스크립트를
쓰기 전에 버리는 이미지 한 장으로 먼저 확인하는 편이 싸다. 하나라도 어긋나면
manifest의 `target.os_suite`부터 바뀐다.

- [ ] **`rpi-image-gen` v2.7.0이 실제로 필요한 일을 하는가.** 태그와 전체 commit
      SHA를 lock 파일에 기록한다.
- [ ] **Raspberry Pi OS Lite arm64 `trixie`가 릴리스 대상으로 준비되어 있는가.**
      아니면 `bookworm`으로 후퇴하고 설계 §6/§7.1의 suite 표기를 함께 고친다.
- [ ] **Docker apt 저장소(`download.docker.com/linux/debian`)에 trixie suite가
      올라와 있는가.** 현재 `deploy/robot/install-pi.sh`가 이 경로를 쓴다.
      없으면 위와 같은 후퇴가 필요하다.
- [ ] `ros:jazzy-ros-base`의 arm64 이미지 digest를 고정했는가.
- [ ] 빌드 호스트의 Docker Engine / Compose plugin 정확한 버전을 lock에 기록했는가.

## 3. BUILD_GO — 이미지와 부속 산출물

native ARM64 빌드 호스트에서:

- [ ] 고정된 입력(§2의 lock)으로 이미지를 빌드한다
- [ ] 산출물이 모두 생성되었는가 — 설계 §7.4
      - `rosy-pi5-<release-id>.img.xz`
      - `rosy-pi5-<release-id>.bmap`
      - `manifest.json`
      - `SHA256SUMS`, `SHA256SUMS.sig`
      - `sbom.spdx.json`
      - `release-notes.md`
- [ ] `python3 deploy/release/manifest.py dist/<release-id>/manifest.json --json` 통과
- [ ] 서명 환경에서 `SHA256SUMS`에 서명하고, 빌드 호스트에서
      `verify_release_files()`가 통과하는가
- [ ] 이미지 안에 비밀이 없는가 — `deploy/release/secret_scan.py`의 matcher를
      마운트한 이미지 트리에 적용한다 (공통 비밀번호, API 토큰, Wi-Fi PSK, SSH 개인키)
- [ ] 이미지에 release 공개키가 들어 있고 개인키는 없는가
- [ ] 필수 systemd unit이 enable 되어 있고 순서가 맞는가 —
      `rosy-release-recover.service`가 `rosy-runtime.service`보다 **먼저** 실행되며
      runtime이 이를 `Requires=`/`After=`로 의존하는가
- [ ] UART overlay는 존재하되 motor service는 비활성인가
- [ ] 기본 `ROSY_RUNTIME_MODE=core`인가
- [ ] 이미지 압축 해제 후 checksum 재검증이 통과하는가

**통과하면 `BUILD_GO`. 이것으로 `BOOT_GO`를 대신하지 않는다.**

## 4. BOOT_GO — 실제 부팅

- [ ] SD에 기록한다 (Raspberry Pi Imager Custom Image 또는 검증된 CLI + bmap)
- [ ] **유선 랜을 연결하지 않은 채** 부팅한다
- [ ] **한 번도 활성화된 적 없는 장비**가 스스로 RECOVERY HOLD에 들어가지 않는가.
      `rosy-release-recover.service`는 모든 부팅에서 runtime보다 먼저 도는데,
      "활성화 레코드 없음"을 홀드로 취급하면 박스에서 꺼낸 로봇이 첫 부팅에서
      스스로 잠기고 자기 첫 설치마저 거부한다. `updater._settled`가
      release-state.json 유무로 "아직 설치 안 됨"과 "레코드를 잃음"을 구분한다 —
      실기에서 이것이 실제로 성립하는지 확인할 것
- [ ] CORE가 기동하고 대시보드가 뜨는가
- [ ] **인터넷 없이** 기동이 완료되는가 — OCI archive 로컬 import가 동작해야 한다
- [ ] runtime mode가 `core`이고 `rosy-motor`/`rosy-io`가 시작되지 않았는가
- [ ] 전원 재인가 후 CORE가 자동 복구되는가

## 5. NETWORK_GO — 두 모드 모두

프로비저닝은 두 운용 모드가 같은 설정 AP를 공유한다(ADR D-26).

### 5.1 공통 — 첫 부팅 프로비저닝

- [ ] `ROSY-SETUP-<short-id>` AP가 자동으로 열리는가
- [ ] `http://10.42.0.1/setup`에서 설정 UI가 뜨는가
- [ ] setup PSK가 **LCD에만** 표시되고 로그·API에는 없는가
- [ ] 국가 코드·SSID·PSK·Robot ID·hostname을 입력할 수 있는가
- [ ] **틀린 PSK를 넣으면** 후보를 폐기하고 설정 AP로 돌아오며, 구체적 실패 사유를
      보여주는가 (기존 프로파일이 보존되어야 한다)
- [ ] 성공하면 설정 AP와 setup endpoint가 **비활성화**되는가
- [ ] 어떤 응답·로그에도 Wi-Fi 비밀번호가 없는가

### 5.2 `SITE_STA` (기본 모드)

- [ ] 사업장 WLAN에 STA로 붙는가
- [ ] 다른 단말에서 `http://rosy-NN.local:8080/dashboard`로 접속되는가 (mDNS)
- [ ] mDNS 미지원 단말에서 `wlan0` IPv4로 접속되는가
- [ ] **인터넷 도달**과 **peer 도달**을 각각 별도로 기록했는가 — 공유기의
      client isolation으로 peer만 실패할 수 있다
- [ ] 인터넷을 차단해도 로컬 대시보드가 유지되는가

### 5.3 `RELAY_AP_STA` (장비별 옵트인)

- [ ] 설정에서 릴레이를 켜고 재부팅하면 STA 연결을 유지한 채 자체 AP가 열리는가
- [ ] 사용자 단말이 **로봇 AP를 경유해** 대시보드에 접속되는가
- [ ] 릴레이 AP의 자격정보가 설정 AP의 것과 **다른가** (NET-005)
- [ ] **상위 업링크를 끊어도** 로봇 AP 서브넷 안에서 조회·제어가 유지되는가
- [ ] 상위 공유기 채널이 바뀔 때 로봇 AP가 따라가는지, 그때 접속이 끊기는지 기록
- [ ] 대시보드 네트워크 카드가 현재 모드를 `RELAY_AP_STA`로 표시하는가

### 5.4 복구 AP

- [ ] 이미 프로비저닝된 장비가 **짧은 WLAN 단절만으로** recovery AP를 열지 않는가
      (`NETWORK_HOLD`에 머물러야 한다)
- [ ] 대시보드에서 다음 재부팅의 recovery mode를 예약하면 동작하는가
- [ ] 전원이 꺼진 장비의 FAT boot partition에 빈 `rosy-recovery` marker를 넣으면
      동작하는가
- [ ] recovery 요청이 **한 번만** 소비되는가 — 다음 부팅에 다시 적용되면 안 된다
- [ ] recovery boot에서 `core` 모드가 강제되고 motor/io가 정지했음을 확인한 뒤에만
      AP가 열리는가
- [ ] setup endpoint가 AP 인터페이스에서만 listen하고, 20분 무활동 후 닫히는가

## 6. UPDATE_GO — 실기 update와 rollback

activation·rollback·전원손실 복구는 tmpdir에서 검증되어 있다
(`test_release_updater.py`). 아래 항목 중 **`deploy/release/`에 구현이 없어 지금은
어떤 테스트로도 실패시킬 수 없는 것**은 ⚠로 표시했다 — WP-6에서 구현하며, 그전까지
이 항목들은 인수 대상이 아니라 구현 대상이다.

- [ ] ⚠ 정상 번들 설치 → `current`가 새 릴리스, `previous`가 이전 릴리스
      (번들 압축 해제와 staging은 아직 구현되지 않았다)
- [ ] **손상된 번들** 거부 — payload를 1바이트 바꾼다 → `CHECKSUM_MISMATCH`
- [ ] **미서명 번들** 거부 → `SIGNATURE_MISSING`
- [ ] **다른 키로 서명된 번들** 거부 → `SIGNATURE_INVALID`
- [ ] **보드 불일치 manifest** 거부 → `MANIFEST_TARGET_MISMATCH`
- [ ] **health 실패 rollback** — 일부러 깨진 CORE 이미지를 담은 번들을 만들어
      90초 bound 안에 이전 릴리스로 돌아오는가
- [ ] **업데이트 중 전원 차단** — 활성화 도중 전원을 뽑는다. 재부팅 시
      `rosy-release-recover.service`가 runtime보다 먼저 돌고, 이전 릴리스가
      `core`로 올라오는가
- [ ] 위 모든 경우에 `rosy-motor`/`rosy-io`가 **시작되지 않았는가**
- [ ] 대시보드에 current/previous/staged와 실패 사유가 표시되는가
- [ ] 롤백 후 이전 릴리스의 컨테이너 이미지가 남아 있는가 —
      `release-retention.md` §4의 prune 금지 규칙이 지켜지는가
- [ ] 활성화 성공 후 staging 디렉터리가 정리되는가
      (`storage.clear_staging`. 롤백 경로에서는 정리하지 않는 것도 함께 확인)
- [ ] 여유 공간 부족 시 업데이트를 **시작하지 않고** 거부하는가
      (`Updater.check_headroom`. 거부 사유에 필요·가용 용량이 숫자로 나오는지)
- [ ] 이벤트가 상한에서 회전하고, **맵은 상한을 넘어도 삭제되지 않는가**

## 6.5 Host Agent — 실기에서만 확인 가능한 것

거부 판정 전체는 `test/test_host_agent.py`가 소켓 없이 검증한다(가드 14개를
하나씩 무력화해 잡히는 것 확인). 아래는 실기가 아니면 확인할 수 없는 것뿐이다.

- [ ] `/run/rosy/host-agent.sock`이 `root:rosy 0660`으로 생성되는가
- [ ] **CORE 컨테이너가 소켓에 연결되는가** — `:ro` 마운트로도 명령이 전달된다
      (`:ro`는 inode 교체만 막는다. 이것이 보호로 오해되면 안 된다)
- [ ] **uid 1000이 아닌 계정**으로 접속하면 즉시 끊기는가
- [ ] **`ROSY_UID`가 로그인 계정과 분리되어 있는가** — 계약 §3의 전제 조건이다.
      Raspberry Pi OS Lite 기본 uid 1000은 사람이 로그인하는 계정이므로, 분리되지
      않았다면 그 계정의 SSH 세션이 `release.install`과 `system.reboot`을 호출할 수
      있다. **이미지 빌드에서 `rosy` 시스템 사용자를 만들었는지 반드시 확인할 것**
- [ ] 재부팅 후 stale 소켓이 남지 않는가 (`/run`은 tmpfs)
- [ ] `nmcli` / `systemctl` 호출이 실제로 동작하는가 — 지금까지 검증된 것은
      인자 리스트 구성뿐이다
- [ ] 감사 로그(JSONL)에 PSK·토큰·개인키가 없는가

## 7. MOTOR_HOLD — 유지되어야 하는 상태

이 절은 통과시키는 것이 아니라 **깨지지 않았음을 확인**하는 것이다.

- [ ] 위 모든 시험 뒤에도 runtime mode가 `core`인가
- [ ] **모터 모드로 승인된 장비에서** 업데이트를 실패시켰을 때, 롤백 뒤에도
      `core`인가 (updater가 이전 record의 mode를 `core`로 강제한다 —
      실기에서 반드시 확인할 것)
- [ ] 열 상승과 저장소 로그 증가를 기록했는가 (설계 §12.3 10단계)
- [ ] UART·모터 승인은 별도 commissioning 절차로 남아 있는가
      (`deploy/robot/verify-motors.sh`, `docs/deployment/power-bench-verification.md`)

모터를 돌리는 순간부터는 이 문서가 아니라 현장 안전 절차의 영역이다.

## 8. 기록

각 게이트마다 남긴다: 날짜, 장비 시리얼, release_id, git revision, 이미지
digest, 통과/실패, 실패 시 오류 코드와 로그. **증거 없는 게이트는 통과로 표시하지
않는다.** 통과하지 못한 게이트는 HOLD로 남기고 그 이유를 적는다.
