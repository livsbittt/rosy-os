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

