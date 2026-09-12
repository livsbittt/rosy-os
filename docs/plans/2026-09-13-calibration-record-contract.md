# 보정 레코드 v1 구현 경계

작성: 2026-09-13. D-43의 로컬 구현 후보이며 운영 승격·실물 인수는 미완료다.

## 파일과 읽기 계약

하나의 YAML 첫 줄에 `# rosy-calibration-record: <JSON>`을 저장하고 나머지는 ROS parameter YAML로 유지한다.
메타데이터와 값은 동일한 임시 파일에서 fsync 후 한 번 교체한다. ROS YAML parser는 comment를 무시하므로
**운영 소비자는 먼저 decode_record(text, expected_context)를 통과해야 한다.** ROS가 YAML을 읽었다는 사실만으로
장치 귀속이나 보정 revision 검증을 대신할 수 없다.

| 필드 | 현재 규칙 |
|---|---|
| schema_version | 정수 1만 지원 |
| context.robot_id | 명시적인 로봇 식별자, 기본 identity 없음 |
| context.hardware_model | 측정 대상 하드웨어 모델 |
| context.geometry_revision | 보정 대상 기구 구성 revision |
| context.sensor_revision | 센서 구성·배치 revision |
| context.data_generation | 이 레코드를 소비할 데이터 generation |
| actor | 호출자가 명시한 작성 주체; 현재 인증 증명은 아님 |
| recorded_at | 저장 시 UTC 시각; 실측 시각·적용 시각의 대체값이 아님 |
| revision | 파일 내 갱신 때 1 증가 |
| previous_digest | 직전 레코드의 digest; 전체 변경 이력 보관은 별도 구현 필요 |
| digest | metadata와 파라미터의 정규 JSON SHA-256; 서명·위변조 인증은 아님 |

context의 5개 값은 모두 필요하며 현재 기대값과 정확히 같아야 한다. 누락·손상·미지원 schema·불일치 시
이전 파일을 유지한다. 기존 일반 YAML에 identity를 자동 부여하지 않는다. context 없는 writer도 bound 파일을
덮어쓸 수 없다. 기존 두 파일 이관 도구는 bound 파일을 일반 YAML로 변환하지 않는다.

## 현재 연결

calib.launch.py의 calibration_context_json, calibration_actor를 명시하면 CalibNode가 context를 검증하고
보정 시작 전 기존 레코드를 확인한다. 저장 시 같은 context와 actor를 전달한다. context를 지정하지 않은
기존 비교 실행은 일반 YAML 경로로 남아 있으며, 이것을 OS 운영 기본값으로 채택하지 않는다.
저장 이후 ROS parameter 응답과 실제 정책 적용은 기존 acknowledgement 구분을 유지한다.

## 운영 승격 전에 필요한 조건

1. Host activation에서 data-working 경로와 ROSY_DATA_GENERATION을 같은 activation record로 공급하는 소스 연결은 구현했다.
   Compose는 generation을 CORE 환경으로 전달한다. bound 보정은 환경값 일치와
   /var/lib/rosy/calibration/<robot-id>/calibration.yaml 경로를 시작 전·쓰기 전에 확인하며 링크 우회를 거절한다.
   실제 Pi의 mount/설치 인수는 남아 있고 수동으로 설정한 환경변수 자체가 신원 인증은 아니다.
2. CORE의 인증된 정비 작업자와 승인된 장치·기구·센서 profile에서 context를 전달한다.
3. 측정 항목별 단위·범위·품질·실측 시각과 적용 revision acknowledgement를 기록한다.
4. 배포 소비자가 raw YAML 대신 검증된 레코드만 전달하도록 한다. 저장 helper는 파일 잠금과 기대 revision 비교를 구현했다.
   잠금은 read/merge/replace 전체를 감싸며 두 번째 writer는 기다리지 않고 거절한다. CalibNode는 측정 시작 시 revision을
   기억하고 저장 때 비교한다. 이것이 보정 동작 전체의 명령권이나 저장 후 정책 적용까지 잠그는 것은 아니다.
5. D-36 업데이트에서 새 working generation으로 복사된 레코드를 검증 후 이관한다. generation만 자동 덮어쓰지 않는다.
   rollback은 이전 working tree를 사용하며 후보 기록을 합치지 않는다.
6. 전원 차단 복구, 이전 runtime의 schema 호환과 ARM64/Pi 재부팅을 검증한다.

현재 시험은 재읽기·revision 연결·5개 context 불일치·손상·자동 귀속/메타데이터 제거 거절과 파일 보존을 확인한다.
실물 장치 신원, 실제 장치 mount, 물리 보정값의 정확성과 인증된 actor는 아직 이 증거에 포함하지 않는다.

추가 검증: Windows와 Linux에서 동시 writer·오래된 revision 거절, 프로세스 강제 종료 후 잠금 회수를 확인했다.
`calibration.yaml.lock`은 안정된 잠금 inode를 유지하기 위해 삭제하지 않는다. 파일의 존재가 활성 writer를 의미하지 않는다.
이관의 새 파일 조건도 잠금 안에서 다시 검사한다. 모든 writer가 이 helper를 사용해야 하며 원시 파일 덮어쓰기를 막는 접근 제어는 아니다.
전원 차단 중 fsync/rename의 장치 파일시스템 내구성과 저장→정책 적용 사이 경쟁은 별도 인수 대상으로 남는다.
