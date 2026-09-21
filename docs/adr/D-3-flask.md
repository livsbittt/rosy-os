## D-3 Flask 완전 대체

**Status:** Accepted (2026-08)

**Context:** 기존 `pinky_navigation/scripts/nav2_web_server.py`(Flask, 560줄)가 존재한다. 병행 운용·레거시 경로 호환도 선택지였다.

**Decision:** 기존 기능 7종을 포함해 전부를 rosy_core FastAPI(`/api/v1/*`)로 재구현한다. 병행 운용·레거시 경로 호환은 하지 않는다. 기능 동등성 체크리스트 충족 시점에 Flask 런치 제거, Web 완성 후 코드 삭제.

**Consequences:** 이중 유지보수 제거, 단일 스택. 누락 방지를 위해 동등성 체크리스트(Impl Plan P0-7)로 관리한다. path/costmap 스냅샷 등 기존 기능이 계약(API Ref §5)에 명시되었다.

---
