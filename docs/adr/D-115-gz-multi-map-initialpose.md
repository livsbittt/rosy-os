## D-115 gz_multi는 스폰 좌표를 map initialpose로 심는다

**Status:** Accepted (2026-09-18). 시뮬 측위 시드다. ROS-SIM GO가 아니다.

**Context:** 각 로봇 odom 원점은 자기 spawn 이다. AMCL 에 map 시드가 없으면 CORE 는
map TF 가 없어 odom (0,0) 을 보고 pose 로 쓴다 (`odometry.odom_owns_pose`).
2026-09-18 factory `gz_multi` 에서 두 CORE 가 둘 다 pose ≈ (0,0) 을 보고, 관제가
겹친 줄 알고 양보를 걸었다. spawn 은 `(-0.2, 1.05)` / `(0.4, 1.05)` 였다.

CORE 는 이미 `POST /api/v1/localization/initialpose` 와 `{ns}/initialpose` 퍼블리셔가
있다. `gz_multi` 가 스폰 뒤 심지 않을 뿐이다.

**Decision:**

- `mode:=nav` (AMCL) 에서 로봇 i 의 map 시드는
  `(spawn_x + (i-1)*spacing, spawn_y, yaw=0)`
- `gz_multi` 가 `{ns}/initialpose` 로 반복 publish 한다. AMCL 이 늦게 구독해도 받게
- odom (0,0) 을 관제 pose 로 승격하지 않는 것이 목적이다. 시드가 곧 현장 GO 는 아니다
- `seed_initialpose` 는 rosy_core 를 import 하지 않는다

**Alternatives:** 운영자가 콘솔에서 initialpose 를 누르는 안은 매 시뮬마다 원점 겹침
양보가 먼저 난다. CORE 가 odom 폴백을 끄는 안은 맵 없는 teleop 화면을 지운다.

**Consequences:** 스폰 숫자와 시드 숫자는 같은 함수다 (`spawn_xy`). pytest 가
Gazebo 를 대신하지 않는다.

**Validation / Transition:** `test_world_profiles.py`, `test_gz_package_contract.py`.
ROS-SIM HOLD.

**References:** D-79, D-81, D-114, D-116.

---
