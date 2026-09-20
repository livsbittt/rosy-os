# control logs

추가만 한다. 형식: [module harness 설계](../../docs/plans/2026-09-15-module-harness-design.md) §4.2.
2026-09-15 이전 이력은 [흡수 실행 계획](../../docs/plans/2026-09-12-rosy-control-absorption-plan.md), [흡수 결과](../../docs/plans/2026-09-12-control-absorption-results.md)와 `git log -- src/control`를 본다.

## 2026-09-15 · uncommitted · docs(harness): start the control harness record
- 변경: `progress.md`, `logs.md` 추가
- 증거: `python3 -m pytest test/test_control_absorption_package.py -q` 6 passed; `PYTHONPATH=src/control:src python3 -m pytest src/control/test -q` 993 passed, 26 skipped, 2 failed (2026-09-15 Windows, 미커밋 WIP 포함 작업 트리)
- gate 변화: 없음. SOURCE GO로, LOCAL은 실패 2건으로 HOLD로, ROS-SIM/ARTIFACT/DEVICE HOLD, FIELD PARKED로 스냅샷 기록
- 결정: D-61 Proposed
- 교훈: 없음

## 2026-09-15 · uncommitted · docs(harness): rerun control LOCAL with the Windows path separator
- 변경: `progress.md` LOCAL 증거와 다음 gate 정정
- 증거: 실패 2건 단독 재실행 2 passed(저장소 루트, 패키지 디렉터리 양쪽); Windows에서 `PYTHONPATH=src/control;src`로 `python -m pytest src/control/test -q` 995 passed, 26 skipped
- gate 변화: LOCAL HOLD→GO. 첫 실행 실패는 POSIX `:` 구분자와 병렬 시험 부하로 추정하며 코드 결함으로 재현되지 않음
- 결정: 없음
- 교훈: 없음

## 2026-09-17 · uncommitted · fix(sensing): stop writing RGB tuples into the BGR map raster
- 변경: S2 — `sensing/map_raster.py`가 계약을 `OCCUPANCY_RGB`로 선언하고 `OCCUPANCY_BGR`을 뒤집어 파생하도록. `WALL_THRESHOLD` 상수화. `web_node.py:render_png` docstring이 색 값을 되풀이하지 않고 출처를 가리키도록. `test_map_raster.py`가 하드코딩 튜플 5곳 대신 상수를 참조. 신규 `test/test_map_raster_color_contract.py` 3건
- 증거: `PYTHONPATH=src/control;src python -m pytest src/control/test -q` 998 passed, 26 skipped (2026-09-17 Windows, 미커밋 WIP 포함 작업 트리)
- gate 변화: 없음. LOCAL GO 유지하되 증거를 995→998로 갱신
- 결정: D-72 (Proposed) 이행 S2. concept 16 §6의 서버-클라이언트 래스터 색 계약을 시험으로 승격
- 교훈: RGB 튜플이 BGR 배열에 그대로 들어가 있었다. `cv2.imencode`가 3채널을 BGR로 읽으므로 PNG의 벽 색이 docstring이 약속한 #e1e0d9가 아니라 #d9e0e1로 나왔다 — 지도에서 면적이 가장 큰 색의 따뜻/차가움이 뒤집혀 있었고 주석만으로는 아무도 못 잡았다. 계약을 RGB로 적고 변환을 한 곳에 모아 같은 실수를 구조적으로 막았다

## 2026-09-17 · 8fdd8d2 · docs(control): D-77 diagnostic surface, CSS/JS token mirror
- 변경: dashboard.html 제목과 AGENTS.md를 진단 화면으로. `const T`가 :root hex와 같음을 시험
- 증거: `PYTHONPATH=src/control;src python -m pytest src/control/test/test_map_raster_color_contract.py test/test_control_launch_boundary.py -q`
- gate 변화: 없음. LOCAL GO. DEVICE HOLD
- 결정: D-77 — 운용자 콘솔은 CORE `/dashboard`
- 교훈: 없음

## 2026-09-18 · uncommitted · feat(control): camera/front publishes sensor-data QoS (D-119)

- 변경: camera_detect_node Image 퍼블리셔가 qos_profile_sensor_data. 구독과 맞춤.
- 증거: `python -m pytest test/test_dds_rmw_contracts.py -q`
- gate 변화: 없음. DEVICE PARKED

## 2026-09-20 · uncommitted · feat(control): ArUco dock tag to relative pose (DNC-007)

- 변경: `control/sensing/dock_tag.py` 신규 — DICT_4X4_50 태그 검출 + solvePnP 상대포즈(x fwd/y left/yaw CCW). 미검출·他 태그는 None. 시험 `test/test_dock_tag.py` 5건(합성 고정: 거리·방위 부호·빈 프레임·他 ID·스펙 검증)
- 증거: `python -m pytest src/apps/control/test/test_dock_tag.py -q` 5 passed. 전체 `src/apps/control/test` 999 passed + 기존 환경 실패 4건(Windows subprocess/launch — clean tree 재현 확인, 본 변경 무관)
- gate 변화: 없음. ROS-SIM HOLD — 실물 도크·카메라 placement 실측 대기. SRS v1.1에 SAF-006/NAV-007/DNC-007 등록

## 2026-09-20 · uncommitted · feat(control): ArUco detector lifecycle + DockType tag spec (DNC-007)

- 변경: `control/sensing/dock_detector.py` 신규 — `ArucoDockDetector`(start/relative_pose/stop, 구조적 적합, core import 없음, D-64 준수). 관측에 confidence(재투영 오차 기반)+at(주입 시계) 추가. `core_features` `DockType`에 tag_family/tag_id/tag_size_m (all-or-nothing 검증, 없으면 검출기 선택 불가)
- 증거: control `test_dock_detector.py` 7건 + `test_dock_tag.py` 5건 = 12 passed (적색→녹색). core `test_docking.py` 103 passed, core 전체 895 passed·10 skipped
- gate 변화: 없음. 배선(factory 주입)은 vision 컨테이너 결정 후 — 미연결 상태의 어댑터는 죽은 코드가 아니라 계약이다

