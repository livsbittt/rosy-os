## D-13 map_id = 맵 파일명 + 체크섬

**Status:** Accepted (2026-08)

**Context:** Fleet 맵 뷰와 Goal 검증(MAP-002)에 맵 동일성 판단 기준이 필요하다.

**Decision:** `map_id`를 `"{파일명}:{내용 체크섬 8자리}"` 형식으로 정의한다.

**Consequences:** 무결성 검증 내장, 중복 맵 자동 구분. 체크섬 변경(재저장) 시 새 map_id가 되는 점은 운용상 주의(버전 관리 정책은 Fleet Maps 화면에서 관리).

---
