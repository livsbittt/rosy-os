## D-108 `--drive`는 계단 2+ 스위치이며 FIELD GO가 아니다

**Status:** Accepted (2026-09-18). 호스트 스위치다. DEVICE/FIELD GO가 아니다.

**Context:** D-96 계단 2는 한 대 0.08 m/s, 계단 3–4는 두 대다. 기본이 관측만
(D-107)이므로 달리려면 명시해야 한다. `--drive`가 pytest 통과를 현장 GO로
읽히면 D-91이다. 한 대만 CORE가 살아 있는데 둘 다 무장하면 계단 2가 실패한다.

**Decision:**

- `--drive`는 arm + PUT limits + teleop를 연다
- 인자 없이 `--drive`면 **두 대** (계단 3–4)
- `--drive rosy_01`처럼 id를 주면 **그 대만** 무장·teleop (계단 2). 다른 대는
  teleop하지 않는다. halt는 양쪽
- 없는 id면 기동하지 않는다
- `--drive`와 `--observe-only`는 같이 쓰지 않는다
- `--drive`는 그 기기 정지·워치독·단일 `cmd_vel` 증거가 있기 전에는 FIELD GO가
  아니다 (D-96)

**Alternatives:** 항상 두 대를 무장하는 안은 계단 2에서 꺼둔 CORE가 arm 실패로
둘 다 halt한다. 한 대 경기를 기본으로 하는 안은 D-96 "한 대만 뛰는 1v1은 없다"와
계단 4를 섞는다.

**Consequences:** `MatchHost.drive_ids`. pytest 무장 시험은 `--drive`.

**Validation / Transition:** `test_cli.py`, `test_loop.py`. FIELD PARKED.

**References:** D-91, D-96, D-104, D-107.

---
