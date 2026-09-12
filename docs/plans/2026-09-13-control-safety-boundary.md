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

다음은 기존 Control의 cliff/tilt/pickup/obstacle/localization 결과를 순수 정책 입력으로 추출하고,
검증된 보정 record와 sensor revision을 evaluator에 묶는 작업이다. 이후 센서 단절·재시작·재보정 시
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
