# Pinky Pro 장비 연결 전 커미셔닝 설계
- 작성: 2026-09-21
- 상태: Accepted for implementation
- 관련: D-33, D-44, D-46, D-51, D-53, D-66,
  `2026-09-20-pi-bench-commissioning-design.md`

## 1. 목적과 경계

내일 Pinky Pro를 연결했을 때 즉흥적인 명령 탐색 없이 G0~G5를 순서대로
실행하고, 중단 후 재개하며, 각 판정을 JSON 증거로 남긴다. 장비 연결 전에는
소프트웨어와 절차만 닫는다. 실제 Pi/모터/LiDAR/카메라가 제공하지 않은 값은
`GO`로 만들지 않는다.

세션 도구는 모터나 Nav2를 직접 움직이지 않는다. G4/G5는 물리 전원 차단,
바퀴 들기, E-stop 준비와 작업자 확인이 필요한 위험 단계다. 도구가 자동으로
그 동작을 실행하면 한 번의 잘못된 옵션이 안전 경계를 우회한다. 대신 기존
검증 명령의 구조화된 결과와 원시 파일 SHA-256을 검증·기록한다.

## 2. 구조

`deploy/robot/commissioning_session.py`가 ROS와 장치에 의존하지 않는 상태기계다.
세션에는 고정된 로봇 번호, expected source revision, 연결 방식(`ssh` 또는
`console`), 생성 시각, 현재 gate와 G0~G5 record가 있다. record는 이전 gate가
`GO`일 때만 추가할 수 있고 한 번 기록한 gate를 덮어쓰지 않는다. 수정이
필요하면 새 세션을 만든다.

`deploy/robot/commission-pinky.py`는 `init`, `status`, `record`, `checklist`
명령을 제공한다. CLI는 임의 shell 문자열을 실행하지 않고 JSON 파일을 읽어
순수 상태기계에 전달한다. 따라서 Windows release PC, Pi의 로컬 console, SSH
세션에서 동일하게 동작한다. 세션 파일은 canonical JSON으로 저장하고 각 gate
record에 evidence 파일의 SHA-256을 포함한다.

## 3. Gate 계약

| Gate | 필요한 구조화 증거 | GO 조건 |
|---|---|---|
| G0 artifact | manifest/signature verification summary | full 40-hex source revision 일치, arm64/Pi 5/Pi OS Lite, rosy_core/rosy_io digest 2개, signature verified |
| G1 install | installer result + identity | exit 0, 요청 robot number와 파생 domain/namespace 일치, runtime `core` |
| G2 readback | `device-readback.sh --json` | `device_runtime=GO`, artifact source/digest/identity 일치 |
| G3 stationary | G2 readback + `/api/v1/robot/state` capture | `core`, E-stop active, linear/angular 0, single final publisher 1 |
| G4 motor | torque-free preflight + deadman trial summary | wheels lifted, hardware cut reachable, configured IDs 응답, 각 trial stop latency/command 결과 기록 |
| G5 hardware | hardware runtime/LiDAR/map/Nav2 summary | fresh scan, expected map identity, bounded one-goal result, final zero/E-stop proof |

모든 gate에는 `schema_version`, `gate`, `captured_at`, `source_revision`,
`robot_number`, `outcome`, `evidence_files`가 필요하다. G4/G5의 작업자 확인은
boolean과 작업자 ID를 모두 요구하며, 빈 문자열이나 `false`는 HOLD다.

## 4. 보정 연결

이 세션은 geometry/motion/camera 보정값의 권위 소스가 아니다. G4/G5의 원시
CSV/JSON/이미지 digest를 보존하여 기존 `commissioning_certificate.py`의
candidate/independent holdout 승격과 `camera_homography.py`의 물리 attestations에
입력한다. 직경, 정지거리, 카메라 거리 오차를 세션 도구의 기본값으로 두지
않는다. 측정 전에는 null/HOLD다.

G5 이후에도 geometry/motion certificate가 active가 아니면 적응 속도 권한은
기존 저속 fail-closed 값에 머문다. Gazebo의 0.172 m 직경과 0.159 m/s 결과는
실기기 인증서에 복사하지 않는다.

## 5. 실패·재개·복구

- record 검증 실패는 세션을 변경하지 않고 비영(0이 아닌) 종료한다.
- 다음 gate를 건너뛰거나 이미 기록한 gate를 덮어쓰면 거절한다.
- expected revision/robot identity가 중간에 바뀌면 새 세션을 요구한다.
- G3 이후 실패 시 운용자는 먼저 E-stop과 `runtime-mode.sh down`을 실행한다.
- release activation 실패는 기존 `release-recover.sh`가 처리하며, 세션 도구는
  이를 대체하지 않는다.
- 네트워크가 끊겨도 console에서 같은 세션 파일을 계속 사용할 수 있다.

## 6. 시험

순수 Python 시험은 정상 순서, gate skip, overwrite, cross-robot/source mismatch,
G0 digest/signature, G2 readback, G3 stationary/E-stop/publisher, G4 위험 확인,
G5 최종 zero를 고정한다. CLI 시험은 canonical file 저장, status/next gate,
실패 시 무변경, secret-like field 거절을 확인한다. 기존 deploy/readback/runtime
시험과 전체 저장소 시험을 재실행한다.

## 7. 카드 A vendor 베이스라인 캡처 (pre-G0)

장비 연결 시 SD 카드는 두 장으로 운용한다. **카드 A는 vendor 출하 이미지 그대로
보존**(플래시 대상 아님), **카드 B에 Rosy OS 서명 이미지를 굽는다.** 카드 A는
아래 세 가지 역할을 가진다.

1. **UNKNOWN 폐쇄**: `docs/plans/2026-09-21-pinky-pro-os-research.md` §11의 11건
   (배포판 문자열, 부트 설정, udev, systemd 자동실행, 핀매핑, pinkylib 위치,
   wifi_setup.sh 본체 등)을 실물에서 읽어 닫는다.
2. **기준값 제공**: G0–G5의 readback 참값과 대체(parity) 체크리스트의 비교 기준.
3. **고장 분리**: G4/G5 실패 시 하드웨어 불량과 Rosy OS 결함을 가르는 control 그룹.

### 절차

- 카드 A를 처음 다루기 전 블록 단위 백업 이미지 + SHA-256을 확보한다(실수 방지 보험).
- 카드 A로 부팅 → SSH(`pinky@192.168.4.1`) → `deploy/robot/capture-vendor-baseline.sh`
  실행 → OUTDIR을 로봇 밖으로 회수한다. ext4를 Windows에서 마운트하지 않는다.
- 스크립트는 **읽기 전용**이며 유일한 쓰기 대상은 증거 디렉터리다. 버스 프로브
  (`i2cdetect`)는 `PROBE_I2C=1` 옵트인이다. 읽기 전용 계약은
  `test/test_capture_vendor_baseline.py`가 고정하고 mutation-proven이다.
- 회수한 원본은 저장소 밖에서 보관한다. site/device 비밀정보 검토와 repository secret
  scanner를 통과한 필요한 증거만 `docs/validation/vendor-baseline-<date>/`에
  SHA256SUMS.txt와 함께 선택적으로 착지한다.

### 판정 연결

- 캡처 결과가 G0 이전 참조 평가(pre-G0 reference)로 남고, 자체로는 어떤 gate도 GO로
  만들지 않는다. vendor 이미지의 동작은 Rosy OS의 증거가 아니다.
- G4/G5에서 카드 B 실패 시, 같은 하드웨어에서 카드 A가 동작하면 Rosy OS 결함,
  카드 A도 실패하면 하드웨어 결함으로 분류한다. 판정 기록은 세션 JSON에 남긴다.
