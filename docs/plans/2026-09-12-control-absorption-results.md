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

### T2 후속 구현: YAML selector와 보정 재소비 (2026-09-13)

- 실제 ROS에서 기존 `safety_node:` selector가 rosy_01 아래에 적용되지 않는 RED 시험을 확인했다.
- 장치 로컬 per-node YAML selector를 `/**/<node_name>`으로 옮겼다. 수치와 실측 timestamp는 변경하지 않았다.
- 보정 저장 시 기존 bare node selector와 업데이트를 같은 wildcard selector로 합친다.
  측정하지 않은 값은 보존하며 중복 bare/wildcard selector가 모호하면 저장을 거부한다.
- ROS Jazzy 시험 2개 통과: 배포된 모든 per-node YAML을 root·rosy_01·rosy_02에서 읽어 값 비교,
  기존 보정 저장→namespaced owner 재소비 및 unrelated node 미적용 확인.
- Control 패키지 전체 회귀: 915 passed, 16 skipped. Windows의 ROS graph skip은 위 컨테이너 증거와 구분한다.
- wildcard는 장치 identity 경계가 아니다. 보정 파일은 장치별 working generation으로 분리해야 한다.
  schema·generation 강제와 TF frame 계약·OS launch 적용은 계속 미완료다.

### T2 후속 구현: OS TF prefix 어댑터 (2026-09-13)

- OS navigation/CORE의 D-4 구현을 대조했다. map은 공통이며 odom·base_footprint·base_link만 로봇 prefix를 갖는다.
- Control의 7개 TF 소비 경로에 RobotTransformBuffer를 연결했다. 기본 prefix는 ROS namespace에서 얻으며,
  frame_prefix 파라미터로 기존 장치 설정을 명시할 수 있다. 이미 한정된 센서 frame과 map은 변경하지 않는다.
- 내부 정책·obstacle packet의 odom/base_link 이름은 로봇 로컬 별칭이다. 어댑터가 실제 TF 이름으로 해석한다.
  base_link와 base_footprint 사이의 변환은 실제 URDF/TF가 제공해야 하며 서로 치환하지 않는다.
- ROS Jazzy 시험: 두 로봇 트리가 공존하는 실제 TF Buffer에서 각 로봇의 map→base 위치를 검증했다.
  root·명시 prefix·없는 변환의 실패도 확인했다. 처리 노드 생성자 시험은 각 Buffer의 namespace 연결을 확인한다.
- TF topic remap은 여전히 격리 시험에서 명시한다. 실제 OS 운영 launch·카메라 장치 frame 설정·
  보정 generation 강제·D-38 단일 명령권 연결과 실물 인수는 남아 있다.
- 검증: Control 915 passed·18 skipped, ROS TF 시험 2개와 처리 노드 연결 시험 1개 통과.
  조사 CSV는 268개 표현식으로 갱신했으며 endpoint 204개의 분류는 동일하다.

### T2 후속 구현: 보정 적용 응답의 의미 (2026-09-13)

- 기존 calib_node는 call_async 직후 적용·AUTO 완료를 표시했다. 응답 없는 요청·거절·timeout 시험을 RED로 확인했다.
- 응답 대기와 승인·거절·실패·5초 timeout을 구분하고 client/timer를 회수한다.
  timeout은 ROS simulation clock이 멈춰도 진행하는 steady clock을 사용한다. 늦은 응답과 중복 요청은 새 완료 상태를 만들지 않는다.
- SetParameters 승인도 `파라미터 저장 확인 — 운전 적용 미확인`으로 기록한다.
  legacy SafetyNode의 일부 값이 생성자에서 cache되므로 ROS parameter 승인만으로 실제 정책 revision 적용을 증명할 수 없다.
- 실제 ROS 서비스에서 승인과 거절을 실행하고 저장된 값과 상태를 확인했다. 드라이버·주행은 실행하지 않았다.
- 검증: 전체 회귀 919 passed·19 skipped, 이후 추가한 owner 부재·중복 요청을 포함한 집중 시험 6 passed,
  격리 ROS acknowledgement 시험 1개 통과.
- D-43의 generation-bound record·장치/geometry identity·다중 파일 transaction·실제 정책 revision acknowledgement는 남아 있다.
  D-36의 data-working mount를 확인했지만 이번 변경에 새로운 저장 schema나 배포 mount를 추가하지 않았다.

### T2 후속 구현: 한 측정의 단일 저장 (2026-09-13)

- compute가 절벽값·구동값을 두 번 저장하던 RED 시험을 확인했다. 이제 한 YAML에 적용 요청과 같은 정밀도의 값을 한 번만 교체한다.
- calib.launch.py의 저장 입력은 calibration_path 하나다. 기존 노드의 save_path/sign_path 직접 설정은 같은 파일을 가리킬 때만 허용한다.
  다른 경로·빈 경로는 이동 보정 시작과 저장 전에 거절하며 abort는 유지한다.
- 정지된 정비 환경에서 사용하는 `python -m tools.migrate_calibration`을 추가했다.
  기존 cliff/drive 원문과 미측정 값을 보존하며, 충돌 또는 기존 출력 파일이 있으면 이관하지 않는다.
- 전체 회귀 925 passed·19 skipped, 이후 추가된 이관 시험 2 passed. 두 파일 중 일부만 저장되는 경로를 제거했으며
  장치 identity·geometry revision·generation envelope와 실제 안전 정책 적용 확인은 계속 미완료다.
- 격리 ROS Jazzy clean colcon build: 1 package finished. 설치 overlay의 calib.launch.py --show-args에서
  namespace와 calibration_path를 확인했다. 노드 기동·이동은 하지 않았다.

### T2 후속 구현: 장치·generation 보정 레코드 후보 (2026-09-13)

- [보정 레코드 v1](2026-09-13-calibration-record-contract.md)의 context와 digest를 같은 YAML에 기록한다.
- CalibNode의 명시 context 경로에 시작 전 검증과 저장 검증을 연결했다. 일반 YAML 자동 귀속·
  불일치 writer·bound record의 메타데이터 제거 이관을 거절한다.
- 전체 회귀 935 passed·19 skipped, 이후 preflight/이관 차단을 포함한 집중 시험 24 passed.
  실제 ROS 보정 생성자·처리 노드 graph 시험도 각각 통과했다.
- 최종 전체 회귀 936 passed·19 skipped. ROS Jazzy clean build 1 package finished 및 설치 launch의
  calibration_context_json/calibration_actor 인자 노출을 확인했다.
- D-43은 Proposed다. 활성 generation mount·인증 actor 공급, 범위/품질 schema, 단일 writer와 실제 정책 revision
  적용·rollback 호환·Pi 인수가 남아 있다. 현재 context 일치는 호출자 제공 값 비교이며 실물 신원 인증이 아니다.

### T2 후속 구현: runtime generation과 저장 위치 연결 (2026-09-13)

- Host DockerRuntime이 activation record의 data_generation을 working mount 경로와 함께 환경에 전달한다.
  runtime.env의 오래된 generation 값은 activation 값으로 대체한다. Compose가 이를 CORE 환경에 전달한다.
- bound CalibNode는 시작 전과 저장 전에 환경 generation과 context가 일치하는지 확인한다.
  /var/lib/rosy/calibration/<robot-id>/calibration.yaml 이외의 경로, 다른 로봇 디렉터리와 링크 우회를 거절한다.
- 배포·delivery·runtime 시험 42 passed·1 skipped, Control 전체 939 passed·19 skipped.
  이후 추가 검증: activation override 5 passed, 저장/경로 16 passed·1 skipped, Linux 경로·symlink 시험 4 passed.
- 실제 Docker Compose config 렌더링에서 generation 전달을 확인했다. 서비스·모터는 시작하지 않았다.
  설치된 Pi의 mount readback·인증 actor/profile 공급·단일 writer·정책 revision 적용은 계속 미완료다.

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
