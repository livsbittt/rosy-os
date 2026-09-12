# Rosy Control → Rosy OS 흡수 실행 결과

작성일: 2026-09-12. 브랜치: `feat/rosy-control-absorption`.

## 현재 단계

2026-09-13: 흡수 변경을 실제 Rosy OS/main에 통합하고 원본 Rogic을 workspace archive로 옮겼다.
파일 해시·보존 경로·연구 문서 편입은 [폴더 통합 결과](2026-09-13-workspace-consolidation-results.md)에 기록했다.

- T0 원본과 목적지 기준선: 완료.
- T1 OS 내부 패키지와 테스트 편입: 완료.
- T2 ROS 연결·설정·보정: 진행 중. 보정 노드의 상대 ROS 이름과 명시적 저장 경로를 반영했다.
- T3–T8 명령권·웹·배포·Pi 인수: 미착수.

후속 구현의 소유권·안전·주행·카메라·보정·배포·평가·OMX 확장점은 [통합 상세 설계](2026-09-12-rosy-os-control-integrated-design.md)에 기록했다. [ROSY ADR Log](../reference/ROSY%20ADR%20Log.md)에 D-37~D-40 Accepted와 D-41~D-44 Proposed로 등록했다. 미검증 기술 선택은 확정하거나 구현 완료로 표시하지 않는다.

이번 변경은 Rosy Control의 Git 추적 소스 가운데 실행 패키지, 테스트, 설정,
launch, 웹 자원, 테스트가 직접 참조하는 도구·지도·검증 fixture를
`src/rosy_control`에 편입했다. 원본 저장소는 수정하지 않았다.

[파일별 이전 대장](2026-09-12-control-absorption-inventory.csv)은 원본 경로,
목적지, SHA-256, 역할, 처리 결과와 후속 검증 단계를 기록한다. 대장 생성 시점에
원본 Git 추적 파일 1,058개와 무시된 로컬 장치 증거 32개를 확인했다. T1에는
320개를 편입했고 738개 문서·legacy 배포 도구·과거 증거는 후속 기능 대조 대상으로 미뤘다.
무시된 장치 증거 32개는 범용 소스 fixture로 간주하지 않고 제외했다.

## 기준선과 검증

### T2 첫 구현 묶음: 보정 노드 경계

- `calib_node`의 publisher/subscriber와 safety parameter service를 상대 이름으로 변경했다.
- `calib.launch.py`에 namespace, save_path, sign_path 인자를 추가했다.
- 원본 개발 checkout을 가리키는 쓰기 기본값을 제거했다. 두 경로를 지정하지 않으면 자동 보정·lidar nudge·저장·적용 요청을 거부하며 abort는 계속 허용한다.
- ROS 없는 `calibration_storage.merge_calibration`로 기존 YAML 갱신을 분리했다. 측정하지 않은 값은 보존하고 손상 mapping·nonfinite 값·교체 실패 시 기존 파일을 유지한다.
- Control 전체 회귀: 907 passed, 10 skipped. pytest cache 쓰기 경고 1건은 캐시 디렉터리 권한 영향이다. 제한 환경의 서버 fixture 실패 후 정상 권한으로 재실행한 결과다.
- ROS Jazzy clean build: 1 package finished, 설치 overlay의 새 storage module import 통과.
- 격리 ROS graph 시험: 실제 생성자를 두 namespace로 실행해 topic 분리와 최종 cmd_vel 부재를 확인했다. 하드웨어 callback은 대체했으며 물리 구동 검증이 아니다.

운영 launch에는 아직 활성화하지 않는다. 기존 보정 YAML의 node selector를 namespace에 맞춰 소비하는 경로, 전체 노드 namespace/TF, 장치 identity/schema, generation 경로 강제, 저장 권한 사전 점검, 다중 파일 transaction 및 적용 acknowledgement는 후속 T2/T3 작업이다. D-41~D-44는 Proposed를 유지한다.

명시한 경로만 사용하므로 기존 calibrator 사용자는 save_path/sign_path를 전달해야 한다. OS 배포에서는 D-36 활성 working generation에 대응하는 경로를 전달해야 하며, 현재 helper 자체는 임의 경로의 generation 소속을 검증하지 않는다. 원본 이전 대장의 hash는 T1 snapshot으로 보존하고 이후 변경은 Git 이력으로 추적한다.

### T2 후속 구현: 카메라·graph 감시 (2026-09-13)

- camera_detect_node의 7개 출력 토픽과 watch_node의 3개 상태 토픽을 상대 이름으로 변경했다.
- 이미지 frame은 camera_frame 파라미터로 장치 profile에서 지정한다. 기본 camera_link는 기존 root 구성과 같다.
- watch는 node namespace를 포함해 조사한다. 다른 로봇의 동명 노드는 local 필수 노드로 계산하지 않으며,
  우리 토픽의 외부 namespace publisher는 별도 오류로 기록한다.
- watch의 기존 legacy 필수 노드·owner 규칙은 보존했다. OS 운영 graph profile로의 전환은 T3/T5에 남아 있다.
- Control 전체: 911 passed, 13 skipped. ROS 없는 Windows에서 graph 시험 3개는 skip이다.
- 외부 네트워크 없는 ROS Jazzy 컨테이너에서 실제 camera/calibration 생성자와 watch DDS endpoint 시험 각각 통과.
  카메라 캡처·하드웨어 callback·속도 발행은 실행하지 않았다. DDS 접근 제어 또는 물리 안전 인증의 증거가 아니다.

전체 namespace/TF·설정 소비 경로와 G2 실물 카메라 결정은 계속 진행 중이다.

실물 접속 확인: 2026-09-13, 이전 주소 pinky@192.168.4.1의 SSH 연결이 timeout으로 실패했다.
장치를 변경하거나 구동하지 않았으며 현재 접속 정보를 요청했다.

### T2 후속 구현: 전체 endpoint 기본값 (2026-09-13)

- 주행·안전·localization·startup·web 노드와 YAML의 endpoint 기본값을 상대 이름으로 변경했다.
- web teleop는 현재 namespace의 cmd_vel_raw로 고정한다. 상태 dictionary의 기존 키는 보존한다.
- 소스 조사 도구 `tools/audit_ros_names.py`와 [조사 CSV](2026-09-13-control-ros-name-inventory.csv)를 추가했다.
  265개 표현식 중 endpoint는 204개이며, 정적으로 확인되는 198개는 상대 이름이다.
  나머지 6개는 parameter·loop·resolver 경로로 수동 확인했다. 이 조사만으로 launch override까지 보장하지 않는다.
- Control 패키지 디렉터리에서 `python -m pytest test -q -p no:cacheprovider`: 913 passed, 14 skipped.
  저장소 루트 실행 시 보조 CLI subprocess import 1건이 실패했으며, 패키지 기준 재실행으로 확인했다.
- 네트워크 없는 ROS Jazzy에서 주요 처리 노드 8개의 실제 생성자를 rosy_01/rosy_02로 각각 실행했다.
  topic/service 해석과 legacy graph의 유일한 cmd_vel publisher(safety_node)를 확인했다.
  TF topic remap은 시험에서 명시했으며 timer·하드웨어 드라이버·실제 구동은 실행하지 않았다.

T2 완료는 아니다. namespace별 YAML node selector, frame prefix와 base frame 계약,
보정 schema·generation, OS launch 연결은 남아 있다. CORE와 legacy SafetyNode 동시 활성화도 허용하지 않는다.

### T0·T1 기준선

| 범위 | 결과 | 의미 |
|---|---:|---|
| 원본 Rosy Control 전체 테스트 | 907 passed, 1 skipped | 흡수 전 로컬 기준선 |
| OS 소유권 RED 시험 | 3 failed | `src/rosy_control` 부재로 기대대로 실패 |
| 편입 후 OS 소유권 시험 | 4 passed | package metadata·import·테스트·OS catalog 소유 확인 |
| 편입 후 Control 전체 테스트 | 898 passed, 10 skipped | 원본 checkout 없이 OS 내부에서 실행 |
| ROS Jazzy clean package build | 1 package finished | `ros:jazzy-ros-base` 컨테이너에서 colcon build, 설치 overlay import 확인 |
| 기존 OS CORE·배포 전체 기준선 | 1405 passed, 10 skipped, 27 failed, 27 errors | 흡수 전 Windows 기준선; Linux script·OpenSSL 부재 영향 포함 |

편입 후 skip 증가는 원본에서 Git에 포함하지 않았던 실물 카메라 artifact와
ROS message 환경에 의존하는 시험 때문이다. 이 차이를 통과로 숨기지 않으며 T6의
Linux/ROS CI와 T7의 Pi 인수에서 닫는다.

기존 OS 전체 기준선의 release signing/delivery 오류는 Windows PATH에서
`openssl`을 실행하지 못한 것이 주원인이었다. DDS identity·publication 일부는
Linux shell 전제도 포함한다. 이 결과는 흡수 전 발생했으며 이번 변경의 회귀로
분류하지 않는다. CORE 로직·API·운영 여정 선택 시험 68개는 별도 정상 권한
실행에서 통과했다.

## 현재 제품 상태

Rosy OS 저장소가 `rosy_control` 소스와 테스트를 소유하기 시작했다. 아직 OS
compose·이미지·CORE API·CommandManager에 연결하지 않았으므로 별도 Control
runtime 없이 Pi가 동작한다고 주장할 수 없다. 특히 기존 SafetyNode와 RosBridge의
최종 속도 발행 경로를 동시에 활성화하면 안 된다.

다음 작업은 T2의 namespace·설정·보정 경계와 T3의 단일 명령권·안전 정책
흡수다. 이 두 단계를 통과하기 전에는 편입된 legacy launch를 OS 기본 모드에
추가하지 않는다.
