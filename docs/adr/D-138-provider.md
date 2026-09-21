## D-138 도크 검출기는 센서 provider 포트를 탄다 — 새 정적 간선 없음

**Status:** Accepted (2026-09-20). 착지 — provider 팩토리, `select_detector`,
services 배선, 계약 15건.

**Context:** DNC-007(ArUco 태그 검출)를 `DockDetector` 프로토콜에 붙이려면
control의 검출기를 CORE 측 상태머신이 써야 한다. D-64는 "rosy_control
import는 센서 어댑터만"으로 묶었고, D-126 S1은 정적 import 자체를 금지하고
`rosy.sensor_provider` 진입점으로만 받는다. 새 진입점·새 정적 간선은 둘 다
과잉이다 — 타는 길은 이미 있다.

**Decision:**

1. **도크 검출기는 같은 provider 포트를 탄다.** `control.sensor_provider`
   에 `make_dock_detector` 팩토리를 추가한다. 새 진입점 없음, 새 정적
   import 없음. D-64의 "센서 어댑터만"은 "provider 포트만"으로 읽는다.
2. **선택은 `select_detector` 하나가 한다.** 기종 명명(`detector="aruco"`)
   + 태그 제원 완비 + provider 팩토리 + 프레임 + 카메라 기하가 다 있어야
   실검출기로 간다. 하나라도 없으면 빈 대본(무관측)으로 떨어지고 상태머신은
   타임아웃 → `DOCK_FAILED`으로 간다. 고장난 provider도 경고 후 같은 길이다.
3. **어댑터는 control 쪽에 산다.** `ArucoDockDetector`는 프로토콜에 구조적
   적합일 뿐 docking 패키지를 import하지 않는다. 매니저가 읽는 것은 세
   메서드와 `range_m`/`x`/`y`뿐이다.
4. **services는 경로만 살린다.** `detector_factory`가 `select_detector`를
   호출하고, 오늘은 provider도 프레임도 없어 항상 시뮬레이션으로 떨어진다
   (동작 불변). 카메라가 오면 `ros_bridge`가 같은 선택에 provider와 프레임을
   꽂는다 — 그때가 카메라 스펙 실측(Task 5) 이후다.

**Alternatives:** bridge에 새 어댑터 + 정적 import — D-64를 다시 여는 것.
core_features에 cv2 직접 import — CORE 이미지(D-66, OpenCV 제외)에서
죽는다. 새 진입점 — 포트 하나로 충분한데 둘을 둔다.

**Consequences:** 태그 제원이 `DockType`에 들어갔다(tag_family/tag_id/
tag_size_m, all-or-nothing). 카메라 기하(내부행렬·왜곡)는 아직 공급자 없음 —
`ros_bridge` 주입 시점에 calibration generation 바인딩(D-47)과 함께 온다.

**Validation / Transition:** provider 3건 + selection 6건 + 기존 docking 회귀.
core 전체 901 passed·10 skipped, control 도크 15건. ROS-SIM/DEVICE 실측은
카메라 placement 뒤.

**References:** D-64, D-126, D-66, D-47, D-137, DNC-004, DNC-005, DNC-007.

---
