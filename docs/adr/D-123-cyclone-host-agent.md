## D-123 웹은 Cyclone을 오버레이에 저장한 뒤 Host Agent 재부팅을 요청한다

**Status:** Accepted (2026-09-18). persist-then-restart. 라이브 RMW 패치가 아니다.

**Context:** RMW는 init 때 로드된다. 웹에서 값을 바꾸고 **다시 뜨면** 새 프로세스가
Cyclone을 쓴다. 그게 맞다. D-121/D-122 가 거절한 것은 init **이후** env 만 바꾸는
거짓 성공과, CORE 가 직접 `reboot()` 를 부르는 것(D-22)이다.

이미 있는 재부팅 도구는 Host Agent `system.reboot` 다. 확인(`confirmed`) 없이는
실행되지 않는다. CORE 는 그 소켓을 중계만 한다.

**Decision:**

- 관리자 `POST /api/v1/system/dds/cyclone` `{confirmed: true}`
- 먼저 오버레이에 `dds.rmw: rmw_cyclonedds_cpp` 를 쓴다 (D-30). 패키지 기본값은
  건드리지 않는다
- 그다음 Host Agent `system.reboot` 를 중계한다. CORE 프로세스 안에서
  `reboot()` / `systemctl` 을 부르지 않는다
- `confirmed` 가 없으면 저장도 재부팅도 하지 않는다
- 에이전트가 없으면 저장은 이미 된 것이 아니라 **전체 실패**로 두지 않는다:
  오버레이는 쓰고, 재부팅 카드는 `available: false` 로 "런타임을 다시 띄우라"고
  말한다. 저장만 되고 재부팅이 안 된 상태를 숨기지 않는다
- 웹 버튼은 확인 대화 뒤 위 POST 만 부른다. FastDDS 선택 드롭다운은 없다 (D-117)
- compose 의 Cyclone 하드코딩은 유지한다. `.env` 로 FastDDS 를 열어주지 않는다

**Alternatives:** 저장만 하고 SSH 재기동은 웹 수정 뒤에 재부팅하라는 요청을 빠뜨린다.
CORE 가 `reboot(2)` 를 직접 부르는 안은 D-22 다.

**Consequences:** 재부팅은 로봇 전체가 잠시 내려간다. 그것이 운영자가 말한 재부팅이다.

**Validation / Transition:** `test_rmw.py`, `test_host_cards.py`, `test_dashboard.py`.

**References:** D-22, D-30, D-117, D-121, D-122.

---
