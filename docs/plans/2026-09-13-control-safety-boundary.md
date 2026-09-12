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
- bounded sweep과 legacy 틸트 역방향 생성은 CORE 어댑터에서 정지한다. 필요한 보정·궤적 검사를 생략한 채 허용하지 않는다.
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
