# Rosy OS 내부 rosy_control 패키지

감지·카메라/OpenCV·보정·주행·안전 판단 로직을 Rosy OS로 흡수한 패키지입니다.
개발·빌드 기준은 Rosy OS 저장소이며 별도 Control 저장소나 설치 절차를 요구하지 않습니다.
외부 API·웹·최종 명령은 rosy_core, 하드웨어는 IO/bringup, 배포·복구는 OS deploy가 소유합니다.

Rosy OS 저장소에서 ROS 2 Jazzy 환경을 준비한 뒤 실행합니다.

```bash
colcon build --base-paths src --packages-select rosy_control
source install/setup.bash
cd src/rosy_control
python3 -m pytest test/ -q
```

소스 편입과 보정 노드 경계 정리는 완료했습니다. 전체 namespace/TF·안전 중재·이미지·Pi 인수는 남아 있습니다.
`calib.launch.py`는 namespace, save_path, sign_path를 받습니다. 저장 경로가 없으면 이동 보정·저장·적용을 시작하지 않습니다.
OS 배포에서는 활성 data generation에 대응하는 경로를 전달해야 합니다(D-43 Proposed).

아래는 편입한 기존 기능 설명입니다. legacy `robot.launch.py`와 `safety_node`를
현재 CORE와 함께 운영 기동하지 않습니다. 상세 상태는
[흡수 실행 결과](../../docs/plans/2026-09-12-control-absorption-results.md)를 따릅니다.

- `calib_node` — 자동 캘리브 `/calib/step auto`: 안정 바닥 IR(4095 무시) → 느린 전진 부호+라이다 요 → 절벽 IR. 상태 `/calib/status` `/calib/phase`.
- `camera_detect_node` — 전면 OV5647. 바닥색 기준 전경 분리로 장애물. 시작 시 AE/AWB를
  수렴시킨 뒤 노출·게인·화이트밸런스를 **고정**합니다(고정 안 하면 게인 1.3배 변화만으로
  판정이 뒤집힘). `/camera/blocked` `/camera/side` `/camera/observation` `/camera/controls`.
  `/camera/cliff`는 **항상 false** — 단안으로는 같은 지면선의 어두운 벽과 어두운 구멍이
  같은 이미지라 판정할 수 없고, 절벽은 바닥 IR이 담당합니다. 어둠은 증거로만 발행됩니다.
  영역 거리(`distance_m`)는 `docs/camera-ground-calibration.md`의 캘리브 후에만 채워집니다.
- `safety_node` — 라이다 3cm, 초음파 2.5cm, IR 절벽, IMU 기울기. 맵 크기로 거리를 정하지 않음. 기울기=`/safety/tilt`(후진). 들어올림=`/safety/pickup`(정지). 벽=`/safety/blocked`
- `wander_node` — 전진 / IR 절벽이면 정지→IR이 풀릴 때까지만 후진→회전 / 벽·카메라 허공·장애물이면 정지→회전. `/wander/cmd` stop|start
- `control_node` — `/goal_distance`, `/goal_rotate`

LCD / LED 화면은 별 패키지 `lcd_control` (`ros2 launch lcd_control lcd.launch.py`).

`STEPS.txt`와 CLAUDE.md의 기존 전체 스택 명령은 이전 동작 비교용 자료입니다.
현재 OS 기동·배포 절차는 저장소 루트 README와 deploy 문서를 따릅니다.
