## D-95 합성 천장 프레임은 DEVICE가 아니다 — 기본 observer는 hold

**Status:** Accepted (2026-09-18). D-91의 games 적용이다.

**Context:** `host/overhead.py`와 합성 ArUco 시험이 LOCAL에 있다. 그 통과를 현장
웹캠 GO로 읽으면 D-91을 우회한다. CLI가 기본으로 `/dev/video0`을 열면 pytest와
실기 실수가 같은 경로가 된다.

**Decision:**

- 합성 프레임·`test_overhead.py`는 LOCAL이다. DEVICE/FIELD로 승격하지 않는다
- 실기 CLI 기본 `--observer`는 `hold`다. 천장 카메라는 `--observer overhead`
- 실제 웹캠으로 구장·공·로봇이 보이는 기록만 D-96 계단 1이다

**Alternatives:** 기본을 overhead로 두는 안은 카메라 없는 호스트가 기동에 실패한다.
합성 통과를 DEVICE로 적는 안은 D-91 위반이다.

**Consequences:** `rosy_games match --config ...`는 카메라를 열지 않고 두 대를
HOLD teleop 0으로 무장한다.

**Validation / Transition:** `src/rosy_games/rosy_games/cli.py` 기본값 `hold`.
`progress.md` DEVICE/FIELD PARKED.

**References:** D-90, D-91, D-94.

---
