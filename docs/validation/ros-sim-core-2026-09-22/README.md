# ROS-SIM core 재실행 절차 — D-162 T5 이후 트리 (2026-09-22)

상태: **대기 (실행 전)** — 실행 후 이 문서의 결과 표를 채우고
`src/core/core/progress.md` ROS-SIM gate를 갱신한다.

## 목적

2026-09-22 D-162 T5가 `bridge/translate.py`(road evidence 선택 context 디코딩)와
`bridge/ros_bridge.py`(sensor snapshot에 context 표시, `import json` 결함 수정)를
변경했다. 2026-09-21 부트 스모크(`docs/validation/ros-sim-core-2026-09-21`)는
변경 전 트리 증거이므로, 동일 방법에 **road/observation 회귀 프로브 2건**을
추가해 재증명한다.

## 실행 환경 (2026-09-21과 동일)

- WSL2 Ubuntu 24.04, ROS 2 Jazzy(`/opt/ros/jazzy`), colcon
- 빌드: 저장소 `src/`에서 `colcon build --symlink-install --packages-up-to core`
- 기동: `ros2 run core core` (launch 미사용, slam_toolbox 불필요)
- 신원(D-33): `ROSY_ROBOT_NUMBER=1` → `rosy_01`, `ROS_DOMAIN_ID=41`,
  `ROS_LOCALHOST_ONLY=1`
- 트리: F: 작업 트리의 스냅샷을 WSL로 복사(2026-09-21 방식 재사용).
  스냅샷 시점 리비전을 evidence/context.txt에 기록한다.

## 절차

1. **빌드·기동**: 위 환경으로 빌드하고 `ros2 run core core`. 12–14초 대기.
2. **기본 프로브** (2026-09-21과 동일, 전부 캡처):
   - `ros2 node list` → `/core`
   - `ros2 topic info /cmd_vel` → Publisher count **1**
   - `ros2 topic info /nav_cmd_vel` → publisher 0 / 구독 1
   - `curl -s http://localhost:8080/api/v1` → 200
   - `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/dashboard` → 200
   - `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/v1/robot/state` → 401
   - 콘솔에 `ros_bridge ready (cmd_vel sole publisher @50Hz)` 존재
3. **road/observation 회귀 프로브 (신규, D-162 T5 대상)**:
   - 유효 payload + context 발행:
     `ros2 topic pub --once /road/observation std_msgs/String "{data: '{\"source\": \"CAMERA_ROAD\", \"stamp\": 10.0, \"map_id\": \"map_260905_update_v2\", \"scene_revision\": \"road-scene-v1\", \"lane\": {\"visible\": true, \"error\": 0.0, \"confidence\": 0.9}, \"stop_line\": {\"visible\": true, \"image_row\": 180.0, \"distance_m\": 0.16, \"confidence\": 0.9}, \"crosswalk\": {\"visible\": false, \"image_row\": null, \"distance_m\": null, \"confidence\": 0.0}, \"signal\": {\"visible\": false, \"colour\": null, \"confidence\": 0.0, \"conflict\": false}, \"context\": {\"id\": \"crosswalk\", \"confidence\": 0.8, \"profile_revision\": \"ctx-crosswalk-v1\"}}'"`
   - malformed payload 발행(깨진 JSON):
     `ros2 topic pub --once /road/observation std_msgs/String "{data: '{not json}'"`
   - **판정선**: 두 발행 모두 콘솔에 NameError/traceback이 없어야 한다.
     특히 malformed 발행은 except 절의 `json.JSONDecodeError` 평가를 강제한다 —
     `import json` 결함이 남아 있으면 여기서 NameError로 프로세스가 죽는다.
     (2026-09-22 수정 전에는 첫 메시지에서 그렇게 되었을 것이다.)
4. **종료**: SIGTERM → `core shutting down` 깨끗한 종료 확인.

## 판정 기준

| 항목 | 합격선 | 근거 파일 (evidence/) |
|---|---|---|
| 노드·부트 로그 | `/core` + `ros_bridge ready` | `ros2-node-list.txt`, `core-boot-console.log` |
| D-2 단일 발행자 | `/cmd_vel` Publisher count 1 | `cmdvel-info.txt` |
| REST/대시보드 | /api/v1 200, /dashboard 200, /robot/state 401 | `api-health.*`, `dashboard-code.txt`, `robot-state-code.txt` |
| road 유효 payload | NameError 없음, 프로세스 생존 | `road-obs-valid.txt`, `core-boot-console.log` |
| road malformed payload | NameError 없음(깨진 JSON 조용히 폐기) | `road-obs-malformed.txt`, `core-boot-console.log` |
| 종료 | SIGTERM 후 깨끗한 종료 | `core-boot-console.log` 말미 |

## 실행 후

- 이 README에 판정(PASS/FAIL)과 결과 표를 기록하고 evidence 파일을 함께 커밋한다.
- PASS면 `src/core/core/progress.md` ROS-SIM을 HOLD→GO로 되돌리고 blocker 대신
  evidence를 적는다. FAIL이면 결함을 `src/core/core/logs.md`에 기록하고 HOLD 유지.
- 범위는 2026-09-21과 동일하게 core 부트+ROS 출력+API다. Gazebo 리그, Nav2/SLAM
  실행, 하드웨어는 본 게이트 밖이다.
