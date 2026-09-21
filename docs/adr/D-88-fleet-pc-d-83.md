## D-88 Fleet 소켓은 사이트 PC 산출물이며 D-83 뒤에 연다

**Status:** Partially superseded by D-154 (2026-09-21). Site Hub는 계속 관제 PC
산출물이지만, FleetAgent를 로봇 이미지에서 제외하고 PARKED로 두는 결정은 대체됐다.

**Context:** 콘솔 v1 gather는 CORE REST다 (D-81). 경로 충돌 대기열도 REST
위에 있다. `rosy_fleet hub --listen`과 CORE `FleetAgent` outbound는 아직 없다.
이것을 로봇 이미지에 넣거나, Task 14 없이 소켓을 열면 사이트 버스와 로봇
런타임이 다시 섞인다 (D-59).

**Decision:**

- `hub --listen`과 `FleetAgent`는 **관제 PC 산출물**이다. `rosy-core` /
  `rosy-io` 이미지에 넣지 않는다
- D-83 `gz_multi robots:=2 mode:=nav core:=true` 증거가 커밋된 트리에서
  다시 나오기 전에는 소켓을 열지 않는다
- REST 콘솔과 경로 대기열은 그 전에도 유효하다 (D-81)

**Alternatives:** 소켓을 로봇에 올리는 안은 D-59 위반이다. REST를 버리고 소켓만
쓰는 안은 콘솔 v1을 멈춘다.

**Consequences:** Fleet ARTIFACT/DEVICE는 PARKED. 로봇 이미지 대상이 아니다.

**Validation / Transition:** `src/rosy_fleet/progress.md`. Dockerfile에
`rosy_fleet hub` COPY가 생기면 이 ADR 위반이다. `test_runtime_slices.py`가
core에 fleet 서버가 없음을 이미 본다.

**References:** D-5, D-12, D-59, D-81, D-83.

---
