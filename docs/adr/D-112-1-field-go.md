## D-112 계단 1 가시성은 호스트 보고이며 FIELD GO가 아니다

**Status:** Accepted (2026-09-18). 천장 마커 체크리스트다. 현장 GO가 아니다.

**Context:** D-96 계단 1은 코너 10–13, 로봇 1/2, 공, 골 20/21이 보여야 한다.
보드에 칩은 있으나 호스트가 “계단 1 보임”을 이름 붙여 말하지 않으면 합성
프레임과 실측을 같은 성공으로 적기 쉽다.

**Decision:**

- `stair1_visibility`는 코너·로봇 ArUco·골 id·공 유실을 보고한다
- `ready`는 네 코너와 두 로봇과 공, 그리고 골 20/21(또는 HSV 입구 설정)이
  보일 때다
- `ready`와 pytest는 FIELD GO가 아니다 (D-91, D-95, D-96)
- `--stair 1 --dry-run`은 기대 id를 찍는다. 라이브는 마지막 보고를 찍는다
- 보드 overlay에 `visibility`를 실어 “FIELD GO 아님”을 같이 쓴다
- OpenCV는 계속 `overhead.py`만. `visibility.py`는 cv2를 import하지 않는다

**Alternatives:** 보드 칩만 두는 안은 계단 1 합격 기준이 운영자 기억이다.
`ready`를 FIELD GO로 승격하는 안은 D-95다.

**Consequences:** 현장 계단 1은 보고를 보고 사람이 `logs.md`에 실측을 적는다.

**Validation / Transition:** `test_cli.py`, `test_preview.py`. FIELD PARKED.

**References:** D-91, D-95, D-96, D-100, D-101, D-111.

---
