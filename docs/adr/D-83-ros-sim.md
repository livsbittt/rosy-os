## D-83 ROS-SIM 최소 재실행 묶음

**Status:** Accepted (2026-09-17). D-79의 실행 목록이다. 이 묶음을 돌리기 전까지
ROS-SIM은 HOLD다.

**Context:** 모듈 progress가 ROS-SIM을 HOLD로 두고 명령이 서로 다르다. 어떤
세션은 `gz_multi`만, 어떤 세션은 Nav2 launch만 돌리고 GO를 주장한다. D-79는
현재 트리 재실행을 요구하지만 **무엇을** 재실행하는지는 비어 있었다.

**Decision:** ROS-SIM GO의 최소 묶음은 이것이다. 하나라도 빠지면 그 모듈은 HOLD.

1. `rosy_core` — Jazzy 컨테이너에서 ROS 출력·`cmd_vel` 단일 publisher 스모크
2. `rosy_control` — sensing/camera/planning 노드 그래프. `robot.launch.py`를
   CORE와 같이 띄우지 않는다(D-38, D-77)
3. `rosy_gz_sim` / `rosy_fleet` — `gz_multi robots:=2 mode:=nav core:=true`
   (Task 14). `relay_tx_hz`·HOLD 지연이 나와야 D-35 후보를 논한다
4. `rosy_navigation` / `rosy_bringup` — `hardware.launch.py` 또는 gz Nav2
   include. 호스트 `test_nav2_profile_limits.py`는 ROS-SIM이 아니다

이 Windows 호스트에서 이 묶음을 돌리지 않는다. 실행 장소는 ROS 2 Jazzy
컨테이너 또는 네이티브 Linux.

**Alternatives:** 모듈마다 제각각 스모크하는 안은 지금 혼선이다. 호스트 pytest로
ROS-SIM을 대체하는 안은 D-79를 어긴다.

**Consequences:** Fleet `hub --listen`과 Device G4는 이 묶음이 아니다.
ARTIFACT는 D-78.

**Validation / Transition:** 각 모듈 `progress.md` ROS-SIM blocker가 위 명령을
가리키게 한다. 재실행 증거 전에는 GO로 쓰지 않는다.

**References:** D-38, D-77, D-79,
[device-validation](../plans/2026-09-13-rosy-os-device-validation-implementation-plan.md),
[swarm bench](../plans/2026-09-08-swarm-formation-slice.md).

---
