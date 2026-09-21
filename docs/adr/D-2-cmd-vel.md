## D-2 자체 cmd_vel 멀렉서

**Status:** Accepted (2026-08)

**Context:** 다중 명령 소스(Web·Fleet·Nav2·향후 Docking)와 E-Stop·모드 중재가 요구된다. `twist_mux` 패키지 사용도 검토했다.

**Decision:** Nav2 velocity_smoother 출력을 `nav_cmd_vel`로 리매핑하고, Command Manager가 **유일한 `cmd_vel` 퍼블리셔**가 되는 자체 멀렉서를 구현한다. E-Stop 상태머신·API·감사 로그와 결합.

**Consequences:** CORE SRS §8.1 요건(우선순위·차단·클리핑)을 완전 구현한다. twist_mux 대비 자체 유지보수 부담이 생긴다.

---
