## D-60 추종은 navigation이 아니라 swarm 패키지다

**Status:** Accepted (2026-09-15). 설계 결정 상태이며 코드 이동과 구분한다.

**Context:** `navigation/`이 NAV와 SWM을 같이 주장한다. `SwarmManager`는 이미
별도 파일이지만 import 경로와 항법 오류 문구가 군집을 알고 있다. 항법 실행기가
팔로워 세션을 생각하면 목표 전달 외에 책임이 생긴다. 모듈 분할 기준은 크기
분할을 금지하고, 요구사항 가문이 겹칠 때만 나눈다(C7/B1).

**Decision:** 로봇 쪽 추종(SWM-001~007)은 `rosy_core.swarm`이 소유한다.
`poses.py`는 참조 표본과 오프셋, `manager.py`는 세션이다. 항법은 단발 목표와
moving-goal 세션만 실행한다. 의존은 swarm → navigation 한 방향이다.
`navigation/swarm.py`는 옮긴 뒤 삭제한다. 이중 import 경로는 두지 않는다.
항법 오류는 군집 이름 대신 moving-goal 세션이라고 말한다.

**Alternatives:** 파일을 `navigation/`에 두고 AGENTS만 고치는 안은 경로가 항법을
계속 가리킨다. 최상위 `swarm.py` 한 파일은 B2(두 역할)를 만족하지 못한다.
채택하지 않는다.

**Consequences:** API/WS는 `svc.swarm`만 본다. `rosy_fleet`은 로봇 SwarmManager를
import하지 않는다. 매핑 세션 C7, Hub listen, 동작 변경은 이번 결정이 아니다.

**Validation / Transition:** navigation 트리의 swarm import 금지 시험, 기존 swarm
호스트 시험의 import 경로 갱신, 기하 대조를 새 경로로 옮긴 뒤 승격 완료로 본다.

**References:** [항법·군집 분리 설계](../plans/2026-09-15-navigation-swarm-split-design.md), [module split](../plans/2026-09-06-module-split-criteria.md).

---
