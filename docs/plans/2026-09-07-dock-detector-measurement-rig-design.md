# 도크 감지기 측정 리그 설계

| 항목 | 값 |
|------|-----|
| Document | ROSY Dock Detector Measurement Rig Design |
| Author | TBD |
| Date | 2026-09-07 |
| Status | Draft |
| Proposed ADR | 없음. 이 사이클의 산출물(판정)이 **D-28 개정**의 입력이 된다 |
| Related | D-28, DNC-002~006, ROSY-DOCK-001; `2026-09-02-docking-station-design.md`, `2026-09-06-module-split-criteria.md` |

## Overview

도킹은 상태머신·충전 이중확인·D-27 인터록·API·도크 계약까지 다 있고 테스트
107개가 덮는다. 실기에서 돌지 않는 이유는 정확히 두 가지다.

1. `services.py`가 `SimulatedDetector(script=[])`를 주입한다 — **빈 대본이라
   도크를 영원히 찾지 못한다.** 실물 검출기가 없다.
2. `capabilities.yaml`과 `deploy/robot/config/*.yaml` 넷 모두
   `docking.supported: false`다.

2번은 한 줄이지만 1번을 고치기 전에 켜면 로봇이 도크를 찾지 못한 채
`DOCK_FAILED`로 떨어진다. 그러니 진짜 병목은 1번, 그리고 1번의 병목은
**감지 방식이 정해지지 않았다는 것**이다. D-28은 그 선택을 의도적으로 유보했다.

이 문서는 감지 방식을 고르지 않는다. **숫자가 고르게 하는 리그**를 설계한다.

## Background & Motivation

### 지금 막고 있는 것은 코드 결정이 아니다

세 후보 중 어느 것도 저장소를 읽어서는 판정할 수 없다. 막고 있는 것은 측정되지
않은 물리적 사실이다.

- C1의 `intensities`가 역반사 테이프를 실제로 가르는가. `sllidar_ros2`가 C1에서
  그 필드를 채우는지부터 미확인이다. `src/rosy_navigation/rviz/map_building.rviz`
  에 저장된 스냅샷은 `Min Intensity: 47` / `Max Intensity: 47` — 상수였을
  가능성을 시사하지만 그 자체가 증거는 아니다.
- IR 배열이 ±20 mm 베이스라인으로 몇 cm부터 유효한가.

답에 따라 설계가 갈라지므로, 추측으로 감지기를 구현하면 재작업 위험이 가장 크다.

### 도크 실물이 없다는 것은 자유도다

도크는 아직 만들어지지 않았다. 그래서 **도크 쪽 형상을 우리가 정할 수 있다.**
이것이 세 번째 후보를 연다.

### 로봇에 실제로 달린 것

| 센서 | 사양 | 도킹 관점 |
|---|---|---|
| RPLIDAR C1 | `sllidar_ros2`, DenseBoost, 360°, 10 Hz | 오늘 돈다 |
| IR ×3 | `UInt16MultiArray` 생 ADC, 미보정, ch 0–2 | **구독자가 트리 전체에 없다** — 발행되고 버려진다 |
| 초음파 ×1 | 0.02–3.0 m, FOV 0.26 rad, 20 Hz | 거리 1축 |
| 카메라 | 드라이버 없음. D-29는 Draft, 워크스페이스에 `v4l2`/`libcamera`/`apriltag` 없음 | 도킹을 여기에 걸지 않는다 |

### 기하가 1순위인 이유

| | 후보 1 역반사 intensity | 후보 2 IR 근접 | **후보 3 기하 전용** |
|---|---|---|---|
| 로봇 쪽 신규 HW | 없음 | 없음 | 없음 |
| 도크 쪽 전자부품 | 없음(테이프) | 없음(패치) | 없음(형상) |
| Gazebo 검증 | 불가 (`gpu_lidar`에 반사율 모델 없음) | 불가 (IR·초음파 미시뮬) | **가능** — 기하는 충실히 나온다 |
| 유효 거리 | 미지 | 수 cm 추정 | 스테이징 0.7 m 전 구간 |
| 미지의 물리 사실 | intensity가 가르는가 | 생 ADC 유효거리 | 거의 없음 |

시뮬 LiDAR는 640 samples/360° = 0.5625°/step이고, 0.7 m에서 점 간격은 6.9 mm다.
15 cm 폭 도크 면에 약 22점이 맞는다 — 포즈 피팅에 충분하고, 실제 C1의 DenseBoost는
이보다 촘촘하다. **후보 3만 측정 없이도 성립 가능성이 계산으로 보이고, 도크 실물
전에 Gazebo에서 끝까지 검증된다.**

후보 2는 탈락이 아니라 **역할이 다르다**. 마지막 수 cm에서 "접점에 닿았나"를
보강하는 자리이고, 이는 지금 `SETTLING`이 도크의 `load_present` 하나에만
의존하는 부분과 겹친다. 이번 리그는 그 판단의 근거도 함께 모은다.

## 센서 기하가 도크 형상에 강제하는 것

`base_link`는 `base_footprint`(바닥)에서 28 mm 위다. URDF의 마운트 오프셋을
바닥 기준으로 환산하면:

| | base_link 기준 | **바닥 기준** |
|---|---|---|
| LiDAR (`rplidar_link`) | x −17 mm, z +67 mm | **z = 95 mm** |
| 초음파 (`ultrasonic_link`) | x +26.7 mm, z +9 mm | z = 37 mm |
| IR 좌/중/우 | x +29.5 mm, y ±20 mm, z −15 mm | **z = 13 mm** |

**바닥에 깔린 깔때기는 LiDAR에 보이지 않는다.** 스캔 평면(95 mm)과 IR
평면(13 mm)이 82 mm 떨어져 있으므로, 도크는 두 높이 모두에 특징을 갖는
최소 ~110 mm 높이의 구조여야 한다. 이것은 리그의 결과가 아니라 리그를 설계하는
과정에서 이미 확정된 사실이고, 도크 기구 설계에 그대로 들어간다.

LiDAR가 base_link보다 17 mm **뒤**에 있고 IR은 29.5 mm **앞**에 있다는 것도
중요하다 — 둘은 x축으로 46.5 mm 떨어져 있어서, 같은 도크를 보고도 다른 거리를
보고한다. 변환을 한 곳에서만 하는 이유다(아래 "프레임 처리").

## 이 사이클이 인정하고 가는 것

기하 후보는 **측정 도구가 곧 감지기의 알맹이다.** "기하 피팅이 충분한 포즈를
주는가"를 측정하려면 피팅을 써야 하고, 그것이 감지기의 핵심이다.

이 사실을 숨기지 않고 설계에 반영한다. 피팅을 **순수 함수**로 만들어 다음
사이클에 `DockDetector` 껍데기만 씌우면 졸업하게 한다. `DockDetector` 경계가
이미 `scan → DockObservation` 모양이므로 이 졸업은 공짜다.

반대로 이것이 감지 방식을 미리 단정하는 것은 아니다. 피팅이 판정을 통과하지
못하면 그 순수 함수는 버려지고, CSV 스키마와 판정 함수는 후보 1·2에 그대로
재사용된다.

## Architecture

### 1계층 — ROS-free 순수 (host pytest가 전부 본다)

`2026-09-06-module-split-criteria.md`의 **C1 기준(host-untestable decision)** 이
이 계층의 근거다. 그 문서는 `ros_bridge.py`에 "host pytest가 볼 수 없는 결정은
더 이상 하나도 없다"로 끝난다. 감지 방식을 고르는 판정이 ROS 노드 안에 들어가면
그 성질이 즉시 깨진다.

| 파일 | 소유 |
|---|---|
| `src/rosy_core/rosy_core/docking/profile.py` (신규) | `DockProfile`(도크 형상 파라미터) + `fit(...) → ProfileFit` |
| `src/rosy_core/rosy_core/docking/probe.py` (신규) | `ProbeRow` CSV 스키마 + `verdict(rows) → ProbeVerdict` |

`ProfileFit`은 `DockObservation`에 진단값(잔차, 사용 점 개수, 적합 점수)을 더한
것이다. 리그는 진단값이 필요하고 상태머신은 필요 없다 — 졸업할 때 껍데기가
진단값을 떨어뜨린다.

배치 근거: ROS-101이 ROS I/O를 `bridge/`에 묶고 이 둘은 ROS-free이며 도킹의
결정이다. `charging.py`·`agent.py`와 같은 자리다.

### 프레임 처리

`fit()`은 ROS 메시지가 아니라 **평평한 배열**(`ranges`, `angle_min`,
`angle_increment`)을 받고, `sensor_offset`(x, y, yaw)을 함께 받아
**base_link 기준 포즈를 직접 반환**한다.

변환을 호출자에게 맡기면 언젠가 한 곳이 빼먹는다. `DockObservation`의 계약이
base_link이므로 경계가 계약을 직접 생산하게 하고, 그 산수를 host 테스트가 덮는다.

### 2계층 — 수집 갈래 둘

| | Gazebo 갈래 | 실기 벤치 갈래 |
|---|---|---|
| 정답 포즈 | **공짜·정확** (우리가 설정한 값) | 자로 잰다 |
| 표본 수 | 수백 (스크립트 스윕) | 수십 (사람이 옮김) |
| 측정 대상 | 후보 3 기하 | 후보 1 intensity, 후보 2 IR |
| 하드웨어 | **불필요 — 지금 돈다** | Pi + C1 + ADC |
| 신규 | `src/rosy_gz_sim/models/dock/` SDF + 스윕 스크립트 | `src/rosy_bringup/rosy_bringup/dock_probe.py` + `deploy/robot/measure-dock-baseline.sh` |

프로브가 `rosy_bringup`에 가는 근거는 `dynamixel_probe.py` 전례다 — 98줄,
argparse 구동, read-only, "무엇을 일부러 하지 않는지"를 docstring에 명시.
벤치 스크립트는 `deploy/robot/measure-dds-baseline.sh` 전례를 따른다.
새 패키지는 필요 없다.

### 3계층 — 하나의 CSV 스키마, 하나의 `verdict()`

이것이 설계의 핵심 결정이다. 두 갈래가 **같은 CSV 스키마**를 쓰고 **같은 판정
함수**를 통과한다. 그래야 세 후보가 비교 가능하고, 판정이 "어느 갈래에서
나왔는지"에 흔들리지 않는다.

한 줄 = 한 표본:

- 출처: `lane`(sim/bench), `candidate`(geometry/intensity/ir)
- 정답: `truth_x`, `truth_y`, `truth_yaw`, `ambient`(실기 조명 조건)
- 관측(기하): `fit_x`, `fit_y`, `fit_yaw`, `residual`, `points`, `confidence`
- 관측(intensity): `int_target`, `int_baseline`
- 관측(IR): `ir_l`, `ir_mid`, `ir_r`

**해당 없는 칸은 빈칸으로 둔다.** 후보별로 CSV를 나누면 판정 함수가 셋으로
갈라지고, 그 순간 비교가 불가능해진다.

## Data Flow

### Gazebo 갈래

1. 도크 SDF를 알려진 절대 포즈로 월드에 배치한다. 형상은 측정용 후보이며
   기구 치수 확정이 아니다.
2. 스윕 스크립트가 로봇을 정답 격자 포즈로 **텔레포트**한다
   (`gz service /world/<w>/set_pose`). 주행이 아니라 텔레포트여야 표본이 빠르고
   정답이 정확하다.
3. `/scan` 한 프레임을 받아 `fit()`을 호출하고 `ProbeRow` 한 줄을 append 한다.
4. 격자: 거리 0.1–1.0 m × 횡 ±0.15 m × 요 ±20°.

정답은 우리가 설정한 값이므로 되읽을 필요가 없다. 이 무료 정답이 이 갈래가
수백 표본을 감당할 수 있는 이유다.

### 실기 벤치 갈래

1. 도크 대역물(형상 목업, 또는 역반사/무광 절반씩 붙인 판)을 자로 잰 위치에 둔다.
2. 한 캡처 = 한 명령:
   `dock_probe --distance 0.5 --lateral 0.03 --yaw 0 --label retro --ambient dim`
3. `/scan`과 `/ir_sensor/range`의 최근 프레임을 같은 `ProbeRow`로 append 한다.
   `ir_sensor/range`는 현재 구독자가 없으므로 이 구독이 트리 최초다.
4. 절차에 `ros2 bag record`를 동시에 돌리라는 한 줄을 넣는다 — 아키텍처가 아니라
   보험이다. 물리 실험은 비싸고, 환산이 틀렸을 때 실험을 다시 하지 않아도 된다.

## 판정 — 기준을 측정 전에 못 박는다

측정 후에 기준을 정하면 원하는 답이 나온다. 그래서 숫자를 먼저 박는다.

**후보 3 기하**

- 스테이징 거리 0.7 m, 횡 ±0.15 m / 요 ±20° 격자 안에서 **획득률 ≥ 95%**
- 거리 0.1–0.7 m 전 구간에서 **횡오차 RMS ≤ 10 mm** — 깔때기가 ±20 mm를
  흡수하므로 여유 2배
- **거짓 양성 0** — 도크 없는 스캔 sim ≥ 500장, 벤치 ≥ 50장에서 단 한 번도
  포즈를 내지 않아야 한다

10 mm 목표는 시뮬 잡음보다 작다. 시뮬 LiDAR의 선언된 잡음이 σ = 20 mm이므로
한 점만으로는 불가능하고, 0.7 m에서 도크 면에 맞는 약 22점을 평균해야
20/√22 ≈ 4.3 mm가 되어 목표 아래로 들어온다. **즉 이 기준은 "피팅이 여러 점을
실제로 쓰고 있는가"를 함께 검사한다** — 한두 점에 의존하는 피팅은 통과할 수 없다.

**후보 1 intensity**

- 모든 측정 거리에서 `min(역반사 반사값) > max(무광 반사값)`. 겹치면 탈락
- 선행 확인: `sllidar_ros2`가 C1에서 `intensities`를 실제로 채우는가.
  상수라면 이 후보는 측정 전에 탈락한다

**후보 2 IR**

- `ir_l − ir_r`이 ±20 mm 밴드에서 단조인가
- 응답이 시작되는 거리. 주변광 조건별로 따로 기록하며, 가장 밝은 조건에서
  응답 시작 거리가 접점 공차 안으로 무너지면 탈락

거짓 양성 0이 가장 강한 기준이다. 저장소가 `SimulatedDetector`의 신선도 주석에서
이미 같은 말을 한다 — *"잃어버린 도크가 확신 있는 오답이 된다."* 포즈를 내지
않는 감지기는 재시도를 부르지만, 틀린 포즈를 확신 있게 내는 감지기는 로봇을
도크가 아닌 곳으로 몰고 간다.

## Error Handling

- `fit()`은 예외를 올리지 않고 불합격을 값으로 낸다. `DockAgent.poll()`이
  "어떤 실패도 예외가 아니라 이 값으로 나온다"로 세운 집 스타일 그대로다.
- 프로브는 스캔 결손·IR 미수신을 빈칸 한 줄로 기록하고 죽지 않는다. 리그가 스윕
  중간에 죽으면 비싼 물리 실험이 날아간다.
- CSV는 한 줄씩 flush append 한다. 크래시가 앞선 줄을 보존한다.
- 프로브는 read-only다. `cmd_vel`을 발행하지 않는다 — D-2에 따라 `cmd_vel`의
  합법 퍼블리셔는 Command Manager뿐이다. Gazebo 스윕의 텔레포트는 시뮬레이터
  서비스이지 로봇 명령이 아니다.

## Testing

새 테스트 파일 둘을 만든다: `src/rosy_core/test/test_dock_profile.py`,
`src/rosy_core/test/test_dock_probe.py`. `test_docking.py`에 넣지 않는 이유는
그 파일이 이미 1157줄이고, `bridge/`의 ROS-free 형제들이 각자 자기 테스트
파일을 갖는 전례(`test_bridge_battery_policy.py` 등)를 따르기 때문이다.

**`profile.fit` host pytest — 네 갈래**

1. 정확한 기하의 합성 스캔 → 정확한 포즈
2. σ = 20 mm 잡음을 넣은 스캔 → **횡오차 RMS ≤ 10 mm** (판정 기준과 같은 숫자)
3. 부분 가림 → `None`
4. **틀린 기하(도크 없는 스캔) → `None`** ← 가장 중요

**`probe.verdict` host pytest** — 손으로 만든 행 집합 → 알려진 판정. 통과와 탈락
양쪽을 모두 덮는다.

**`test_module_criteria.py`가 새 모듈에 거는 제약** — 이 테스트는 `rosy_core`
안의 모든 `hasattr`/`getattr` 사용을 리터럴 allowlist와 **집합 동등성**으로
강제한다. `profile.py`와 `probe.py`는 둘 중 어느 것도 쓰지 않는다. 선언된 멤버와
타입 있는 dataclass만 쓰면 이 제약은 자동으로 지켜지고, 실제로 그렇게 설계한다.
(`manager.py`가 `safety`·`battery`를 `getattr`로 만지는 것은 기존 allowlist에
verdict가 기록된 항목이며 이번 작업이 건드리지 않는다.)

**Gazebo 갈래 자체가 통합 테스트다.**

**실기 갈래의 유일한 검증은 DOCK_GO**이며,
`docs/deployment/pi5-acceptance-checklist.md` §7.6에 측정 항목을 추가한다.
`ros_bridge`의 도킹 조정부가 이 저장소에서 임포트되지 않는다는 §7.6의 전제는
그대로 유지된다.

실행:

```bash
cd src/rosy_core && python -m pytest test/test_docking.py -q
```

## 이번 사이클이 하지 않는 것

명시적으로 범위 밖이다.

- `ScanDockDetector`를 `services.py`에 배선하지 않는다 — 판정 통과가 게이트다
- `docking.supported`를 `true`로 바꾸지 않는다
- 도크 기구 치수를 확정하지 않는다. SDF 형상은 측정용 후보다
- 상태머신(`manager.py`)을 손대지 않는다
- `DockType.detector` 플러그인 배선을 하지 않는다 — 판정이 어느 후보를 고를지
  아직 모른다
- 카메라·D-29에 의존하지 않는다

## Consequences

- 감지 방식이 **기록된 숫자로** 결정되고, 그 기록이 저장소에 남는다.
- 판정이 후보 3을 통과시키면 다음 사이클은 `profile.fit`에 `DockDetector` 껍데기를
  씌우고 `services.py` 배선과 capability를 여는 짧은 작업이 된다.
- 판정이 후보 3을 떨어뜨리면 CSV·판정·프로브는 그대로 남고 후보 1·2 측정이 이어진다.
  버려지는 것은 `profile.py` 하나다.
- 도크 기구 설계는 이 문서의 "센서 기하" 절(스캔 평면 95 mm / IR 평면 13 mm /
  최소 높이 ~110 mm)을 입력으로 받는다.
- D-28은 감지기를 유보한 상태로 유지된다. 판정이 나온 뒤 개정한다.

## Open Questions

- `sllidar_ros2`가 C1에서 `intensities`를 채우는지 — 후보 1의 선행 조건이며
  `ros2 topic echo /scan --field intensities` 한 번으로 확인된다.
- 도크 형상의 구체적 후보: 알려진 간격의 수직 기둥 2개 vs 특정 각도의 V 오목면.
  기하 갈래의 첫 스윕이 이 둘을 비교하는 것으로 시작한다.
- 실기 벤치의 주변광 조건 구간을 몇 개로 나눌지. IR은 주변광에 민감하다.
