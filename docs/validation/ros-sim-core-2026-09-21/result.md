# ROS-SIM core 재실행 — 현재 트리 부트 스모크 (2026-09-21)

판정: **PASS** — `src/core/core/progress.md` ROS-SIM HOLD 해소 증거.
2026-09-20 Gazebo 시도에서 기록된 부팅 결함(`AttributeError: self.core_common` —
9b77daa에서 유입, 6ff2cb8에서 수정, `docs/logs.md` 770행 경유)이 현재 트리에서
재현되지 않음을 확인했다.

## 실행 환경

- WSL2 Ubuntu 24.04, ROS 2 Jazzy(`/opt/ros/jazzy`), colcon
- 빌드: `colcon build --symlink-install --packages-up-to core` — 7패키지 성공 (22.5s, stderr는 setuptools 경고뿐)
- 기동: CI 부트 스모크와 동일 형식 — `ros2 run core core` (launch 미사용, slam_toolbox 불필요)
- 신원(D-33): `ROSY_ROBOT_NUMBER=1` → `rosy_01`, `ROS_DOMAIN_ID=41`, `ROS_LOCALHOST_ONLY=1`
- 트리: F: 작업 트리의 tar 스냅샷(2026-09-21)을 WSL로 복사해 빌드. `.git`은 스냅샷에서 제외 —
  리비전 증거는 별도 기록: 스냅샷 직후 기준 HEAD `26daba0`(같은 날 커밋 85fcb42→53a131c→26daba0로
  스냅샷 당시 작업 트리가 대부분 반영됨). 본 문서는 트리 스냅샷 방식과 그 한계를 명시한다.

## 결과 (evidence/ 파일 근거)

| 항목 | 결과 | 근거 |
|---|---|---|
| 노드 기동 | `/core` 발견 | `ros2-node-list.txt` |
| 부트 로그 | `ros_bridge ready (cmd_vel sole publisher @50Hz)` → `core up: robot_id=rosy_01 model=Pinky Pro` → `api server on 0.0.0.0:8080` | `core-boot-console.log` |
| D-2 최종 발행자 | `/cmd_vel` **Publisher count: 1**(CORE bridge 단독), 구독 0. `/nav_cmd_vel`은 publisher 0 / 구독 1 — Nav2 출력은 CORE 구독으로 귀속 | `cmdvel-info.txt`, `navcmdvel-info.txt` |
| ROS 출력 그래프 | `/odom`, `/scan`(구독), `/battery/voltage`, `/batt_state`, `/imu_raw`(구독), `/map`, `/plan`, costmap, Nav2 transition_event, 현재 트리 신규 토픽(`/robot/hitl_request`, `/camera/preview/compressed`, `/line/observation`, `/road/observation`, `/motor/ready`, `/display/info`)까지 관측 | `ros2-topic-list.txt` |
| REST API | `GET /api/v1` → 200 `{"name":"core","api_versions":["v1"]}`, `GET /dashboard` → 200 | `api-health.*`, `dashboard-code.txt` |
| 인증 | `GET /api/v1/robot/state` → 401 `UNAUTHORIZED`(토큰 없음) — 토큰 계약 정상 동작 | `robot-state-code.txt`, `robot-state.json` |
| 종료 | SIGTERM 후 `core shutting down` 깨끗한 종료 | `core-boot-console.log` 말미 |

## 범위와 한계

- 본 실행은 **core 부트 + ROS 출력 + API**의 재증명이다. Gazebo 리그 기동, Nav2/SLAM
  스택 실행, 하드웨어 매핑은 본 실행 범위가 아니다(gz_sim·navigation은 별도 게이트,
  하드웨어는 G5 DEVICE 트랙).
- 이 트리는 당일 다른 세션의 진행 작업(traffic signal/UI 커밋)을 포함한 **현재 작업
  트리**다. 스냅샷 시점과 커밋 시점 사이의 미반영 편차 가능성을 위해 위 트리 절차를
  명시한다. 재판정이 필요하면 같은 절차로 재실행한다.
- LOCAL 게이트(Windows 1026 passed)와 본 ROS-SIM 증거는 상호 보완이며, DEVICE 승격에는
  여전히 ARTIFACT(서명 이미지)→G0–G5가 필요하다.

## 방법 재현

빌드: WSL에서 저장소 스냅샷 `src/`에서 `colcon build --symlink-install --packages-up-to core`.
실행: identity 환경변수 설정 후 `ros2 run core core`, 12–14초 대기 뒤
`ros2 node list` / `ros2 topic list` / `ros2 topic info /cmd_vel` / curl 프로브.
