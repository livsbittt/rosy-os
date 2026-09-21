## D-20 Swarm 하이브리드: 오케스트레이션 Fleet / 폐루프 추종 로봇 탑재

**Status:** Accepted (2026-08-29) — D-12 확장(미션 오케스트레이션 Fleet 전용 원칙은 유지)

**Context:** 기존 Formation 설계는 Leader pose를 Fleet이 받아 Follower별 목표를 계산·전송(약 2 Hz)하는 완전-중앙 방식이었다. 왕복 지연으로 추종이 울퉁불퉁해지고, Fleet 단절 시 형상이 즉시 붕괴된다. 로봇 자체가 군집 모드를 지원하면 좋은지 검토 요청이 있었다.

**Decision:** 하이브리드로 간다. Fleet은 지정·릴레이·중단 판단만(Leader pose 스트림 ≥10 Hz 수신 → Follower WS 릴레이 ≥5 Hz, `swarm/follow` 명령 1회). **폐루프 추종 계산은 로봇 탑재**(SWM-001~006): rosy_core이 pose 스트림을 소비해 moving-goal Nav2(≤2 Hz 갱신)로 추종하고, 스트림/Fleet 단절 시 로컬 HOLD(SWM-004). v2 대안(로컬 pure-pursuit cmd_vel 소스)은 CMD-001 등록 인터페이스로 예약.

**Consequences:** 추종 품질 향상(로컬 10 Hz 스트림 소비), Fleet 단절에도 형상·안전 로컬 유지, Fleet 부하 최소화. 로봇 코드에 follow 상태머신·스트림 타임아웃이 추가됨(복잡도 증가). Fleet은 릴레이 지연(≥5 Hz 보장) 품질에 영향을 주므로 적합성 테스트(P4-6)에 포함.

---
