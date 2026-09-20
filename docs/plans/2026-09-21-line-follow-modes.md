# IR·카메라 차선 추종 모드 실행 계획

1. 감지기와 manager의 실패 테스트를 먼저 작성한다.
2. 카메라 detector를 튜닝 가능하게 확장하고 IR detector를 추가한다.
3. CORE `LineFollowManager`, protocol status, 서비스 배선을 구현한다.
4. ROS bridge의 관측 구독과 단일 Navigation 후보 속도 경로를 연결한다.
5. `/api/v1/line-follow` 조회·모드 변경 API와 Dashboard 선택 UI를 구현한다.
6. Control camera/IR publisher와 설정을 연결한다.
7. 결정론적 시뮬레이터를 실행해 JSON trace를 보존한다.
8. API Reference, 진행 기록, harness를 갱신하고 전체 회귀 후 커밋·병합한다.

완료 조건은 호스트 테스트와 시뮬레이션 통과, 단일 `cmd_vel` 발행자 유지,
`nav.lane_lost` 발행, Dashboard의 세 모드 선택 가능이다. 실제 Pinky 교정과
주행은 DEVICE/FIELD HOLD다.
