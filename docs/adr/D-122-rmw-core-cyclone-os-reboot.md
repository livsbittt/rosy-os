## D-122 잘못된 RMW는 다음 CORE 기동에서 Cyclone으로 고친다. OS reboot가 아니다

**Status:** Accepted (2026-09-18). D-121의 "거절"을 "다음 기동에서 교정"으로 바꾼다.

**Context:** RMW는 init 뒤에 안 바뀐다. 그래서 "자동으로 설정하고 재부팅하면 된다"는
말이 맞다 — **다시 띄우면** `apply_cyclone_rmw` 가 새 프로세스에서 먹는다. 다만
(1) 커널 `reboot` 는 UART 오버레이·Host Agent 영역이고 CORE가 부르면 안 된다
(D-22). (2) RMW만 고치려면 `rosy-core` 컨테이너/`rosy-runtime.service` 재기동이면
충분하다. (3) compose 는 이미 Cyclone을 박아 두므로 장치 기본 재기동은 이미
Cyclone이다. (4) 웹에서 `system.reboot` 를 누르면 로봇 전체가 내려가 모터·도크까지
같이 죽는다.

D-117 은 FastDDS 프로파일이 없다. 그래서 D-121 의 "틀린 RMW면 기동 실패"는
대시보드조차 못 띄운다. 다음 기동에서 Cyclone으로 **고치고 뜨는** 편이 맞다.

**Decision:**

- `apply_cyclone_rmw` 는 빈 값과 FastDDS/기타 값을 **Cyclone으로 고친다.** 거절하지
  않는다
- 이 교정은 **이 프로세스의 env** 다. `rclpy.init` 전에만 유효하다
- 이미 떠 있는 이웃 노드(같은 스택의 Nav2 등)는 **런타임 재기동**으로 같이 뜬다.
  `systemctl restart rosy-runtime.service` 또는 compose `up`. 커널 `reboot` 가
  아니다
- 웹은 계속 보고만 한다. RMW 적용 버튼·`system.reboot` 연동을 만들지 않는다
- Host Agent `system.reboot` 는 호스트 권한(네트워크·릴리스)용이다. RMW 도구가
  아니다
- `CYCLONEDDS_URI` 추측 덮어쓰기는 여전히 하지 않는다 (D-121)

**Alternatives:** 웹 확인 뒤 Pi reboot 는 동작은 하지만 폭발 반경이 RMW보다 크다.
틀린 RMW로 기동을 막는 안은 고칠 화면이 없다.

**Consequences:** `ros2 run rosy_core` 가 FastDDS env 로 불려도 CORE는 Cyclone으로
뜬다. 같은 셸의 다른 노드는 그 셸을 다시 열어야 한다.

**Validation / Transition:** `test_rmw.py`. DEVICE PARKED.

**References:** D-22, D-117, D-121.

**Amendment (2026-09-18):** CORE 기동이 FastDDS env 를 Cyclone으로 고치는 결정은 유지한다.
운영자가 웹에서 **저장 후 재부팅**하는 경로는 D-123. 라이브 env 패치는 여전히 없다.

---
