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

## 2026-09-20 · uncommitted · feat(safety): evidence-gated adaptive speed authorization

- 변경: add immutable geometry/sensor and motion-envelope candidate certificates, independent holdout promotion, conservative clearance braking, runtime drift downgrade, and a reducing-only numeric speed cap handed to CORE.
- 증거: focused Control tests `37 passed`; final Control gate `1038 passed, 26 skipped` after synchronizing the launch-test fixture with the declared empty web-port defaults; CORE package `895 passed, 11 skipped`.
- gate 변화: SOURCE and LOCAL GO for the pure policy and handoff. ROS-SIM/ARTIFACT/DEVICE/FIELD remain HOLD. No speed above `0.014 m/s` is enabled.
- 결정: calibration output is inert until a separate-session holdout promotes it, and an active envelope may reduce but never create motion authority.
- 교훈: geometric fit, sensor status, stopping evidence, runtime conditions, and final command authorization must remain separately auditable.

## 2026-09-20 · uncommitted · feat(control): replace fixed 8 cm escape cap with measured diameter bound

- 변경: the live escape proposal now carries the calibrated circumscribed diameter and searches only within that diameter and the independently measured straight corridor. Reverse wins equivalent choices, but front/rear evidence remains authoritative. Execution stops as soon as rotation clearance returns and refuses proposals missing the measured bound instead of falling back to 0.08 m.
- 증거: focused escape planner/executor/adapter tests `30 passed`; wider recovery/adaptive-speed/certificate/calibration set `102 passed`; final full Control gate `1038 passed, 26 skipped`; exact-map findings are recorded in `docs/validation/map-260905-update-v2-2026-09-20/result.md`.
- gate 변화: none. SOURCE behavior is covered; active CORE/Nav2 recovery integration, ROS-SIM complete traversal, DEVICE and FIELD remain HOLD.
- 교훈: a diameter is a maximum search envelope, not a commanded distance; every tick must shrink authority from current observed room and never expand an open episode.

## 2026-09-20 · uncommitted · feat(camera): add validated tunable ground homography

- 변경: add a ROS-free camera homography evaluator that recomputes fit and independent holdout residuals, binds processed image size/rotation/profile revision, requires physical validation evidence, and refuses board-relative X as robot lateral. Add bounded ROS tuning parameters, transient status, a session-only enable command, and diagnostic dashboard switch/read-only checks while preserving pinhole as the default.
- 증거: TDD focused `15 passed`; camera/web regression `161 passed, 10 skipped`; full Control from the required package cwd `1038 passed, 26 skipped`; launch-test fixture now supplies the two declared empty web-port defaults.
- gate 변화: none. SOURCE behavior is covered. ROS-SIM/DEVICE/FIELD remain HOLD because no complete ChArUco profile, independent Pinky Pro captures, measured-distance readback, or physical stopping trial was supplied.
- 결정: an approximate profile may be loaded and tuned but cannot become active; validation checks are node-owned and cannot be clicked through in the dashboard. Runtime tuning remains bounded ROS configuration, while the dashboard enable is intentionally session-only.
- 교훈: a low residual on calibration correspondences does not prove the image preprocessing contract, robot coordinate frame, unseen distances, or a physically locked camera mount.

## 2026-09-20 · uncommitted · feat(control): ArUco dock tag to relative pose (DNC-007)

- 변경: `control/sensing/dock_tag.py` 신규 — DICT_4X4_50 태그 검출 + solvePnP 상대포즈(x fwd/y left/yaw CCW). 미검출·他 태그는 None. 시험 `test/test_dock_tag.py` 5건(합성 고정: 거리·방위 부호·빈 프레임·他 ID·스펙 검증)
- 증거: `python -m pytest src/apps/control/test/test_dock_tag.py -q` 5 passed. 전체 `src/apps/control/test` 999 passed + 기존 환경 실패 4건(Windows subprocess/launch — clean tree 재현 확인, 본 변경 무관)
- gate 변화: 없음. ROS-SIM HOLD — 실물 도크·카메라 placement 실측 대기. SRS v1.1에 SAF-006/NAV-007/DNC-007 등록

## 2026-09-20 · uncommitted · feat(control): ArUco detector lifecycle + DockType tag spec (DNC-007)

- 변경: `control/sensing/dock_detector.py` 신규 — `ArucoDockDetector`(start/relative_pose/stop, 구조적 적합, core import 없음, D-64 준수). 관측에 confidence(재투영 오차 기반)+at(주입 시계) 추가. `core_features` `DockType`에 tag_family/tag_id/tag_size_m (all-or-nothing 검증, 없으면 검출기 선택 불가)
- 증거: control `test_dock_detector.py` 7건 + `test_dock_tag.py` 5건 = 12 passed (적색→녹색). core `test_docking.py` 103 passed, core 전체 895 passed·10 skipped
- gate 변화: 없음. 배선(factory 주입)은 vision 컨테이너 결정 후 — 미연결 상태의 어댑터는 죽은 코드가 아니라 계약이다

## 2026-09-20 · uncommitted · feat(dock): detector rides the sensor provider port (D-138)

- 변경: `control/sensor_provider.py`에 `make_dock_detector` (cv2 지연 import). `core_features` `select_detector` — aruco 명명+제원 완비+provider+프레임+기하가 다 있어야 실검출기, 아니면 빈 대본. `services.py` detector_factory가 `select_detector` 호출 (오늘은 항상 시뮬레이션, 동작 불변)
- 증거: provider 3건 + selection 6건 신규. core 전체 901 passed·10 skipped, control 도크 15건. flake8 신규 파일 무경고 (services.py E306 기존 건 제외)
- gate 변화: 없음. 카메라 프레임·기하 주입은 Task 5 실측 뒤 ros_bridge 몫

## 2026-09-20 · uncommitted · feat(control): lane error and loss tracker (NAV-007)

- 변경: `control/sensing/lane.py` 신규 — 하단 밴드 이진화+열 중심 횡오차(고전 CV, YOLO 없음), `LaneTracker`(3초 유예 후 정지 요구, 재목격 해제). `LANE_MAX_LINEAR_M_S = 0.10`. 시험 `test/test_lane.py` 10건(합성 차선: 중앙·좌우 부호·빈 바닥·추적·유예·상실·재획득·미목격)
- 증거: `test_lane.py` 10 passed (적색→녹색 — 밝기합/픽셀수 단위 혼동 1건은 구현 결함으로 적색 확인 후 수정). 전체 1019 passed + 기존 환경 실패 4건(본 변경 무관)
- gate 변화: 없음. 조향 소비(오차→각속도)와 nav.lane_lost 이벤트 배선은 노드 몫 — evidence까지만 닫힘

## 2026-09-21 · uncommitted · feat(mapping): complete the exact v2 Gazebo map

- 변경: `map_260905_update_v2`의 16개 벽을 직접 읽는 감사기가 점이 아닌 반경 `0.086 m` 본체의 spawn 연결 구성공간을 계산하고, 접근 가능한 곳의 unknown/occupied/out-of-raster 비율을 각각 판정한다. 실제 주행 경로는 밀폐 포켓을 제외한 모든 관측 포켓을 방문한다.
- 증거: Gazebo Harmonic `final_22`에서 52/52 waypoint, odom `13.754679 m`, 접근 가능한 unknown `0.0%`, occupied `0.0%`, 충돌 중첩 없음, 최소 표본 본체 여유 `0.021789 m`. CORE 단독 최종 `cmd_vel` publisher와 Fleet `online=true`, `map_id=occupancy:326966090e60`를 같은 실행에서 읽었다. 상세 수치는 `docs/validation/map-260905-update-v2-2026-09-21/result.md`.
- gate 변화: Control 전체 ROS-SIM은 HOLD 유지. 정확한 v2 월드의 mapping/CORE/Fleet 슬라이스는 GO지만, camera/calibration/safety-policy 전체 노드 그래프와 실기기는 이 실행이 증명하지 않는다.
- 결정: 전체 이미지 unknown 비율 대신 실제 본체가 도달 가능한 구성공간을 합격 기준으로 삼고, 밀폐 포켓 비율은 별도 공개한다.
- 교훈: 반복되는 얇은 벽에서는 scan matcher가 정확한 simulation odom을 잘못 굽힐 수 있다. 시뮬레이션에서는 live scan을 Gazebo model-pose odom에 직접 래스터화해야 재현 가능한 정답 비교가 된다.

## 2026-09-21 · uncommitted · feat(control): selectable IR and camera line following (D-143)

- 변경: CORE dashboard/API에서 `OFF`, `IR_LINE`, `CAMERA_LINE`을 배타적으로 선택한다. Control은 IR/영상 evidence만 발행하며 CORE manager가 adaptive speed와 조향을 만들고 기존 단일 `cmd_vel` 경로가 최종 중재한다. `rosy-io` 이미지와 hardware launch에 V4L2 camera fallback 및 Pinky 0x08 I²C ADC publisher를 연결했다.
- 안전: 원본 영상 header stamp 기반 stale, malformed/저신뢰/미검출 즉시 zero, 3초 loss latch, 모드 전환 상태 잠금, 0.10 m/s 별도 상한을 적용했다.
- 증거: 폐루프 운동학 simulation에서 3.5 cm 횡오차가 IR -0.03 cm, camera 0.006 cm로 수렴하며 stale/loss 정지 통과. 외부 IR calibration YAML, V4L2 exposure/white-balance 잠금 readback, mode/evidence revision 원자적 handoff를 추가했다. Control `1084 passed, 26 skipped`; CORE `955 passed, 11 skipped`; root `1008 passed, 13 skipped`; Fleet `332 passed, 5 skipped`; OMX `10 passed`; Games `101 passed`. `rosy-io:dev` 빌드와 이미지 내부 3개 line-follow executable, OpenCV 4.6.0, launch argument readback도 통과했다.
- gate 변화: SOURCE/LOCAL GO. ROS-SIM은 detector/manager 폐루프 증거만 추가되었고 전체 graph gate는 HOLD. ARM64 artifact, Pi camera/I²C readback, 물리 교정과 실제 차선 주행은 ARTIFACT/DEVICE/FIELD HOLD.
- 결정: D-143. 센서는 motion authority가 아니며 관제는 CORE API만 사용한다.
