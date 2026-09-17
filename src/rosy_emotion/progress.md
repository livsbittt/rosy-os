---
module: rosy_emotion
logical_modules: [M02]
owner: 장치
last_verified: { commit: "uncommitted", date: 2026-09-15 }
gates:
  SOURCE:
    state: HOLD
    blocker: "패키지 경계(서비스 노드·info_screen 계약)를 고정하는 host 계약 시험이 없다. test_nav2_hardware_slice.py의 이미지 제외 단언은 패키지 내용을 읽지 않으므로 SOURCE 증거가 아니다(ARTIFACT 근거로만 쓴다). 렌더러 동작은 LOCAL이 다룬다"
  LOCAL:
    state: GO
    evidence: "16 passed (2026-09-16 재실행, Windows, 미커밋 WIP 포함 작업 트리) — info_screen 렌더·battery_color 임계값"
    cmd: "PYTHONPATH=src/rosy_emotion python3 -m pytest src/rosy_emotion/test/test_info_screen.py -q"
  ROS-SIM:
    state: HOLD
    blocker: "rclpy set_emotion 서비스 노드가 있음. ROS 2 Jazzy 컨테이너 재실행 필요, 미실행"
  ARTIFACT:
    state: HOLD
    blocker: "hardware 프로필이 이미지에 배선되지 않았다. core/io 이미지 제외는 test/test_nav2_hardware_slice.py::test_io_image_packages_nav2_without_slam_or_aux_drivers가 고정한다"
  DEVICE:
    state: PARKED
  FIELD:
    state: PARKED
adrs: [D-57]
plans:
  - docs/plans/2026-09-12-rosy-os-module-evaluation-maintenance-design.md
  - docs/plans/2026-09-15-module-harness-design.md
---
## 지금 상태

- `set_emotion` 서비스(LCD GIF)와 PWR-003 info-card 렌더러(`info_screen.py`, ROS-free PIL)를 제공한다.
- 작업 트리에 미커밋 변경이 있다: `AGENTS.md` 수정, `emotion/AGENTS.md` 신규. LOCAL 증거는 이 작업 트리 기준이다.
- `test/test_copyright.py`·`test_flake8.py`·`test_pep257.py`는 ament_copyright/flake8/pep257을 import한다. 이 호스트에는 설치되어 있지 않아(`ModuleNotFoundError`) 실행할 수 없고, 시도해도 증거로 세지 않는다.
- `deploy/robot/Dockerfile`에는 core/io 두 이미지만 있고 rosy_emotion을 포함하지 않는다. 하드웨어(LED/lamp/IMU/ADC/emotion) 프로필은 아직 배선되지 않았다.

## 다음 gate

1. ROS 2 Jazzy 컨테이너에서 `set_emotion` 서비스 노드 graph/parameter smoke를 실행해 ROS-SIM을 되돌린다.
2. 서비스 노드·info_screen 경계를 고정하는 host 계약 시험을 추가해 SOURCE를 채운다.
3. hardware 프로필이 `deploy/robot/Dockerfile`에 배선되면 ARTIFACT blocker를 서명 artifact 발행으로 바꾸고 DEVICE/FIELD를 PARKED에서 HOLD로 올린다.

## 현재 유효한 금지사항

- PIL 렌더링은 `rosy_emotion`에만 둔다. `rosy_core`는 `display/info` JSON만 발행한다.
- `info_screen.py`의 320×240 landscape 출력 계약을 깨지 않는다(LCD 코드가 회전/리사이즈로 가정).
