# Control 안전 판단의 CORE 소비 경계

작성: 2026-09-13. D-38/T3의 로컬 구현. D-42는 실제 센서 공급자와 성능 인수 전까지 Proposed다.

## 현재 구현

CommandManager는 profile로 제한한 수동·navigation 후보를 SafetyManager.evaluate_candidate에 전달한다.
SafetyManager.bind_policy는 같은 프로세스에서 동작하는 동기 evaluator와 calibration revision을 등록한다.
판단자는 ROS publisher나 최종 명령권을 갖지 않는다. 실제 속도 발행자는 기존 RosBridge 하나다.

| 요청/결과 | 의미 |
|---|---|
| command_id | CORE가 각 출력 평가에 부여하는 ID. 외부 API request ID와는 별도다. |
| source | 수동 명령의 등록 source 또는 navigation 입력 경로. Fleet 업무 세션 ID를 대신하지 않는다. |
| calibration_revision | 등록된 evaluator가 사용하는 revision. 현재 caller가 제공하며 보정 레코드 loader 연결은 미완료다. |
| now / observed_at / expires_at | 동일 프로세스 monotonic 시각. ROS simulation clock이나 다른 호스트의 시각을 직접 비교하지 않는다. |
| linear/angular_limit | 이미 제한된 후보를 더 낮출 수만 있는 비음수 유한 상한 |
| disposition | allow, limit, stop |
| reason | stop의 내부 원인. 기존 safety source 및 audit 경로로 표시한다. |

결과 ID·source·revision이 요청과 일치하고, 관측이 미래가 아니며 완료 시각까지 만료되지 않아야 한다.
판단 유효기간은 최대 0.5초, evaluator 호출 시간은 최대 10ms로 제한한다. 유효 결과도 선택 후보·모드가
평가 중 바뀌거나 e-stop이 걸리면 발행하지 않는다. 이 시간 검사는 함수가 반환된 뒤 수행한다.
동기 함수의 무한 대기를 선점하는 기능은 아니므로 evaluator에는 I/O·sleep·원격 호출을 넣을 수 없다.
실제 센서 정책의 최악 처리시간과 모터 deadman은 별도 인수 대상이다.

## 정지와 재계획

판단 누락·오류·만료·형식 불일치·stop은 수동/navigation 후보를 폐기하고 기존 EMERGENCY/e-stop 경로를 사용한다.
서비스는 상태 요약을 갱신하고 navigation 목표도 취소한다. 기존 관리자 release API로 해제한 뒤 새 명령이 필요하다.
정지 중 들어온 navigation 속도는 해제 후 사용할 후보로 보관하지 않는다.

유효한 limit 결과의 0 상한은 일시적인 속도 제한이며 e-stop으로 바꾸지 않는다. 정적 장애물 앞에서
안전한 새 경로를 탐색하는 동작에 쓸 수 있다. 실제 공급자가 장애물 종류·경로 가능성·sensor freshness를
올바르게 구분하는지는 아직 검증하지 않았다. 이 경계가 장애물 탐지나 경로 생성을 대신하지 않는다.

## 활성화와 남은 작업

safety.control_policy_required는 명시적인 boolean이며 기본 false다. true인데 evaluator가 없으면 이동 후보는
정지로 처리한다. bind_policy를 호출해도 필수 검증이 켜진다. 현재 운영 profile은 이 기능을 켜지 않는다.
외부 API·DDS message schema는 추가하지 않았다.

기존 Control의 순수 판단과 CORE 내부 소비 경계는 아래와 같이 연결했다. 다음은 실제 센서 콜백의 관측 공급과
검증된 보정 record 적용을 sensor revision에 묶는 작업이다. 이후 센서 단절·재시작·재보정 시
이전 관측과 후보를 무효화하고, legacy 최종 publisher를 제거한 운영 graph에서 검증해야 한다.
API 권한 검증은 수행했지만 새 UI의 브라우저 검증이나 Pi 물리 인수는 수행하지 않았다.

## 기존 Control 판단의 순수 함수 추출

`rosy_control.control.command_gate.evaluate_command`를 추출하고 기존 SafetyNode가 이를 사용하도록 연결했다.
입력은 센서 분류 결과·관측 실패·localization 준비 여부·명령 나이·보정 trial 영역이며,
출력은 semantic 속도·사유·후보 폐기 여부다. 전방 장애물은 명시적인 후진/회전을 일괄 차단하지 않는다.
혼합 이동 명령의 일부 축만 제거되어 경로가 바뀌면 전체를 정지시킨다.

기존 틸트 역방향 생성은 `legacy_tilt_recovery=True`로 비교 노드에서만 보존했다.
기본 함수는 전진 후보를 역방향 명령으로 바꾸지 않는다. CORE의 복구 동작은 별도 후보로 중재되어야 한다.
음수·nonfinite 명령 나이는 새롭게 거절한다. 정상 시각/유한 명령의 비교는 이전 `90f4d7f` 실제 tick 코드와
13,824개 조합에서 출력 및 기존 정지 사유가 일치했다. 새 경계 시험과 노드 어댑터 집중 시험은 28개 통과했다.
Control 전체 회귀 시험은 953 passed·20 skipped이며, 격리 ROS에서 8개 노드의 두 namespace 생성 시험도 통과했다.
이 ROS 시험은 센서 입력과 모터 동작을 수행하지 않는 생성·이름 경계 검증이다.

이 함수만으로 센서 evaluator 연결이 완료되지는 않는다. 원시 센서의 freshness/geometry 검증,
보정 gain·상한·실제 swept footprint 검사, drive-sign 변환은 기존 노드에 남아 있다.
CORE는 이 결과와 검증된 보정 record를 하나의 관측 snapshot에 묶어 소비해야 하며,
현재 운영 profile은 여전히 통합 정책을 활성화하지 않는다.

## Control → CORE 내부 연결

`SafetyManager.bind_control_policy(CommandPolicy)`가 실제 Control 판단을 호출하고 그 결과를
기존 `SafetyDecision`으로 변환한다. 새 ROS publisher나 외부 API는 추가하지 않는다.
CORE의 ROS 패키지 의존성에 `rosy_control`을 명시했고 두 패키지의 colcon build 및 설치 overlay import/연결을 확인했다.

- `GateSnapshot`은 변경 불가능한 입력 묶음이며 session·sequence·적용 revision·관측 시각·만료 시각을 함께 가진다.
- 정책 인스턴스는 새 session을 만들고 비어 있는 상태에서 시작한다. 다른 session/revision, 역순 sequence는 거절한다.
  반복 조회나 같은 관측 시각의 새 sequence로 유효기간을 늘릴 수 없다. 재전송은 센서 heartbeat가 아니다.
- snapshot의 시각은 같은 프로세스의 monotonic 기준이다. 실제 공급자는 필요한 센서 중 가장 오래된 관측과
  가장 이른 만료를 사용해야 한다. 현재 이 공급자는 실제 ROS 센서 콜백에 연결하지 않았다.
- CommandManager가 후보 명령의 freshness를 소유한다. snapshot은 센서 상태이며 과거 명령 나이를 새 명령에 전파하지 않는다.
- 일반 obstacle/trajectory 제한은 zero limit으로 재계획 여지를 보존한다. pickup·localization 상실·필수 관측 실패는 e-stop이다.
- 최종 simulation actuation이 등록되지 않은 bounded sweep과 legacy 틸트 역방향 생성은 CORE 어댑터에서 정지한다. 필요한 보정·궤적 검사를 생략한 채 허용하지 않는다.
- 정책 재등록 시 manual/navigation 후보를 폐기한다. 새로운 정책이나 보정 revision으로 과거 명령을 재실행하지 않는다.

revision은 아직 호출자가 제공하는 적용 식별자다. 파일 digest 검증/loader나 실제 센서 보정 적용의 증거로 취급하지 않는다.
서비스의 자동 구성과 운영 profile 활성화는 미완료이며, 이 연결은 전체 운용 동등성을 증명하지 않는다.
격리 ROS 출력 시험 5개에서 기존 차단/제한과 Control 전방 정지·명시적 후진 출력을 검증했다.
실제 센서 스트림, 모터 deadman, Pi 물리 동작과 관리자 UI 인수는 별도 남아 있다.

### 센서 관측 기록의 유효기간 연결

기존 `Observations`에 `policy_window`를 추가하고 `CommandPolicy.update_observations`에서 사용한다.
필수 stream이 하나라도 누락·invalid·stale이면 snapshot을 폐기한다. 원본 stamp가 있는 stream은
수신 시각에서 전송 지연을 빼서 유효기간을 계산하며, 가장 오래된 필수 관측을 기준으로 최대 0.5초만 허용한다.
반복 timer 조회는 수신 시각을 갱신하지 않는다. 실제 적용 revision이 정책 revision과 달라도 snapshot을 폐기한다.

이 메서드는 센서 기록 갱신 및 분류와 같은 직렬 callback group에서 호출해야 한다.
관측 수집/분류의 원자성을 다른 thread에서 임의 호출해 보장하는 API는 아니다.
CORE 시험에서는 실제 Observations → CommandPolicy → CommandManager 경로의 전송 지연/만료를 확인했다.
운영 SafetyNode 콜백과의 배선, 필수 stream 목록의 장치 profile 연결과 보정 파일 적용은 아직 남아 있다.
검증: Control 전체 957 passed·20 skipped, CORE 정책 연결/안전 집중 시험 38 passed.

### 후보 명령에 종속되는 차체 형상 판단

SafetyNode의 narrow-footprint 허용은 센서 공통 boolean이 아니다. 보정된 속도가 0.014m/s 이하이고
각속도가 0.0001rad/s 미만인 직진 후보에만 적용된다. 이 조건을 `lidar_guard.translation_footprint_eligible`로
추출하고 기존 노드가 직접 호출하도록 연결했다. 정상 입력 8,640개 조합은 기존 조건식과 일치했다.
음수 스캔 나이와 양수가 아닌 차체 반경은 명시적으로 거절하도록 보강했다.

CORE용 생산 snapshot에 현재 노드의 `blocked` 값만 복사하면, 이전 저속 직진에 허용된 차체 형상을
다른 고속/회전 명령에 잘못 적용할 수 있다. 운영 연결 전 다음 계산을 후보 명령별로 이전해야 한다.

| 계산 | 현재 위치 | CORE 연결 요구 |
|---|---|---|
| narrow-footprint 선택 | 순수 함수 + 기존 SafetyNode 호출 | 후보 속도·보정 gain·원시 geometry를 함께 평가 |
| tracked obstacle hold | `safety/obstacles.py` | 현재 후보의 진행 방향과 같은 pose/track snapshot 사용 |
| bounded swept clearance | SafetyNode 최종 gate | 보정된 실제 후보와 관측 나이로 sweep 재계산 |
| drive gain/sign | SafetyNode 최종 gate | 제한·궤적 검사·실제 발행 순서와 보정 revision 일치 |

따라서 이 단계에서 운영 센서 노드의 기존 boolean 출력을 CORE에 자동 배선하지 않는다.
필요한 명령별 geometry 경계를 구현한 뒤 단일 최종 publisher graph로 전환한다.
검증: Control 전체 958 passed·20 skipped, 실제 ROS 두 namespace의 처리 노드 생성 시험 통과.

### CORE 후보별 translation geometry 소비

`GateSnapshot.translation`에 변경 불가능한 `TranslationEvidence`를 함께 담을 수 있다.
`CommandPolicy.evaluate`는 CORE가 선택한 현재 속도로 `command_translation_bumpers`를 호출한다.
같은 snapshot에서 저속 직진이 허용되어도 빠른 직진이나 회전 혼합 후보는 radial 판단으로 돌아간다.
방향별 보정 gain은 저속 직진 eligibility 계산에 반영하며, 기존 다른 센서의 obstacle/rear 제한을 해제하지 않는다.
이 gain 계산은 실제 모터 출력에 보정을 적용했다는 증거가 아니다.

생산자는 이전 후보의 footprint override가 섞이지 않은 radial front/rear와 hysteresis 기준값,
거리·형상·보정 gain 및 같은 프로세스 monotonic 기준 scan 수신/원본 관측 시각을 제공해야 한다.
현재 명령의 형상 판단을 기존 `blocked` boolean 복사로 대체할 수 없다.
0.2초가 지난 geometry로 narrow-footprint를 허용하지 않으며 0.5초 초과 geometry는 거절한다.
snapshot을 다시 발행해도 geometry 자체의 시각은 갱신되지 않는다.

`update_observations(..., translation=...)`로 센서 clock과 형상 증거를 함께 전달한다.
한 정책에서 geometry를 사용하기 시작한 후 새 snapshot에서 빠지면 기존 snapshot을 폐기한다.
목록 등 변경 가능한 geometry 값, 잘못된 boolean, nonfinite 값과 범위 밖 gain도 거절한다.

검증: CORE 전체 717 passed·5 skipped, Control 전체 959 passed·20 skipped.
이후 확장한 실제 ROS 출력 시험 7개와 만료 보강 후 집중 시험 11개(Control)·41개(CORE)가 통과했다.
운영 센서 producer의 배선, 보정 record 적용, tracked obstacle/전체 sweep·drive 변환과 Pi 인수는 남아 있다.

### CORE 후보별 tracked obstacle 소비

`TrackedEvidence.capture`는 기존 track/camera packet과 odom pose를 복사하고, 동일 ROS clock의
원본 stamp를 수신 시점의 monotonic clock으로 변환한다. 원본 dict/list를 이후 수정해도 snapshot은 바뀌지 않는다.
각 packet은 32KiB 이하, track은 최대 64개로 제한한다. 캡처는 센서 producer에서 수행하고,
CORE는 고정된 packet을 읽어 기존 `camera_hold`·`observation_risk`·`collision_risk`를 재사용한다.

`GateSnapshot.tracking`과 `update_observations(..., tracking=...)`를 통해 현재 후보의 선속도로 위험을 평가한다.
정적 장애물의 replan 및 이동/불명 장애물의 wait는 zero limit이며 관리자 e-stop 해제를 요구하지 않는다.
거리 없는 카메라 장애물도 일시 제한이다. pose·track·camera 누락/만료/잘못된 geometry는 기존 e-stop이다.
tracking을 한 번 사용한 정책에서 이후 snapshot의 tracking이 빠지면 기존 관측을 폐기한다.

기존 legacy 함수와 동일하게 정적 replan 중 선속도 0인 후보의 회전 여유는 별도의 전방위 형상 gate가 소유한다.
이 예측은 기존의 선속도 기반 상대 충돌 모델이다. 회전 혼합의 전체 arc sweep나 Nav2 우회 경로 생성을 대체하지 않는다.
현재는 정책 제한을 CORE에 전달했으며, replan 이유에 따른 backend 재계획·완료 상태 전달은 T4에서 연결해야 한다.
운영 ROS callback에서 snapshot을 생산하는 배선과 보정 적용·전체 sweep·drive 변환·Pi 인수는 남아 있다.

검증: Control 전체 961 passed·20 skipped, CORE 전체 719 passed·7 skipped.
이후 확장한 실제 ROS 출력 시험 8개에서 추적 장애물의 zero 출력까지 확인했다.

### 최종 sweep 공통 함수와 적용 순서

기존 SafetyNode의 최종 sweep 분기를 `motion_sweep.command_sweep_clearance`로 추출하고 기존 노드가 호출한다.
complete scan·source/receive age 0~0.2초·회전 중심 추정·양의 차체 반경·선속도 0.014m/s 이하·각속도 0.1rad/s 이하를 요구한다.
기존 0.8초 horizon과 이전 명령의 정지 잔여 이동 여유를 유지한다. 전체 회전 pivot 증거, 검증된 polygon,
보수적인 body circle 순서로 기존 계산을 재사용한다. 증거가 없으면 None, 충돌 여유가 없으면 0 이하를 반환한다.

현재 SafetyNode는 `drive gain → angular gain → profile/lease 공통 scale → sweep → drive sign → publish` 순서다.
CORE의 현 SafetyDecision은 상한을 낮추는 계약이므로, 보정으로 달라진 최종 후보를 검사하기 전에
단순히 `bounded_motion` 허용을 켜면 기존 경로와 동등하지 않다. CORE 연결 전 실제 발행 후보·보정 revision·허용 환경을
같이 고정하고 그 후보에 sweep을 적용해야 한다. 기존 domain 227 시뮬레이션 전용 활성 조건은 변경하지 않았다.
이 추출 단계에서는 CORE bounded motion을 허용하지 않았다. 후속 조건부 연결은 아래 simulation actuation 절을 따른다. 물리 장치의 정지 거리나 실물 운행은 승인하지 않았다.

검증: 공통 sweep/footprint 집중 시험 52개, Control 전체 962 passed·20 skipped,
실제 ROS 두 namespace 처리 노드 생성 시험 통과. 실제 모터의 궤적/제동 인수는 남아 있다.

### 보정 이후 최종 발행 후보 준비

`control/actuation.py`의 `prepare_command`가 방향별 linear/angular gain과 profile/limited-sensor 상한을
기존 순서로 적용한다. 선속도·각속도에 동일한 scale을 적용해 혼합 명령의 비율을 유지한다.
gain의 적용 영역은 원래 요청의 angular 값도 사용한다. 이전 gate에서 회전을 제거했다고 해서
legacy 틸트 복구 후보를 새 직진 보정 영역으로 재분류하지 않는다.

결과 `PreparedCommand`는 sweep에 사용할 `linear/angular`와 방향 부호를 반영한 `motor_linear`를 고정한다.
기존 SafetyNode는 한 lease 시각으로 gains/caps를 읽고, 준비된 후보로 sweep과 decision 기록을 수행한 뒤
고정된 motor 값을 발행한다. 검사와 발행 사이에 방향 값을 다시 읽지 않는다. 잘못된 gain/cap/sign은 정지한다.
이 변경은 보정 데이터의 출처나 적용 권한을 새로 인증하는 기능이 아니며, CORE에는 아직 자동 연결하지 않았다.

검증: 기존 유한 입력 수식 960개 조합 일치, Control 전체 973 passed·20 skipped.
이후 추가한 실제 노드 발행 구간 시험을 포함한 actuation 집중 시험 12개와 실제 ROS 노드 생성 시험이 통과했다.
CORE에서 정책 제한과 보정 변환의 역할을 분리하고, 같은 보정 revision의 PreparedCommand를
최종 sweep·발행·보정 acknowledgement에 연결하는 작업이 남아 있다.

### 시뮬레이션 한정 CORE 최종 출력 연결

`SafetyManager.bind_simulation_actuation`으로 immutable `SimulationActuation`을 명시적으로 등록할 수 있다.
등록과 매 출력에서 `ROS_DOMAIN_ID=227`, `GZ_PARTITION=pinky_calmap227`, 실제 simulation clock 활성 콜백을 확인한다.
기존 운영 profile과 서비스 부팅에서 자동 등록하지 않는다. 물리 장치용 활성화 경로가 아니다.

처리 순서는 `CORE 정책 제한 → 보정/공통 scale → 최종 후보 sweep → motor sign → 기존 RosBridge 발행`이다.
보정된 후보는 0.014m/s·0.1rad/s와 CORE manual/nav/session 상한을 모두 지킨다.
유효한 최종 simulation actuation이 있을 때만 bounded 후보의 전체 sweep을 사용하며,
제자리 전체 회전 허용이 없다는 이유만으로 검증 가능한 제한된 arc를 일괄 차단하지 않는다.
충돌 sweep은 zero limit, 증거/환경/보정 revision 누락이나 만료는 기존 e-stop으로 처리한다.

정책과 보정의 revision이 일치해야 하며, 정책 재등록은 기존 보정을 무효화하고 후보를 폐기한다.
선택 결과와 보정·관측 만료를 함께 검사하고, 준비 중 profile/session 상한이 달라져도 발행하지 않는다.
정책 평가부터 최종 준비까지 합한 시간 예산은 10ms다. 함수가 반환한 뒤 검사하므로 무한 대기를 선점하는 기능은 아니다.
실제 ROS 시험에서 발견한 첫 출력의 모듈 import 지연은 초기화 시 sweep/NumPy 모듈을 준비하도록 수정했다.

이 revision과 complete-scan/pivot 증거는 아직 명시적 호출자가 공급한다. 장치 identity에 묶인 보정 파일 검증과
실제 센서 producer의 증거 생성·동기화, 4,096점/64 footprint vertex 최대 입력에서의 장치 성능,
운영 활성화·보정 ACK·실물 제동 인수는 아직 증명하지 않았다.
검증: 최종 CORE 전체 725 passed·10 skipped, Control 전체 974 passed·20 skipped,
격리 ROS 출력 시험 10개 통과. ROS 시험은 실제 use_sim_time 파라미터와 DDS 발행을 사용하며 물리 모터를 연결하지 않는다.
