## D-105 호스트 정지는 스페이스와 보드 /stop이며 양쪽 safety/stop이다

**Status:** Accepted (2026-09-18). 호스트 입력이다. DEVICE GO가 아니다.

**Context:** 설계 §5는 스페이스·창 닫기·예외가 양쪽 `POST /api/v1/safety/stop`을
부른다고 적는다. 예외와 finally는 이미 `halt()`다. 스페이스와 보드 정지는 없었다.
보드가 CORE FastAPI를 직접 치면 D-101을 깨뜨린다.

**Decision:**

- 라이브 루프는 스페이스를 보면 다음 사이클에서 빠져 `halt()`한다
- 미리보기 `POST /stop`은 **같은 노트북 서버**만 친다. CORE URL을 열지 않는다
- `/stop`은 플래그만 세운다. HTTP 스레드에서 teleop와 동시에 estop하지 않는다
- 창 닫기·프로세스 종료는 기존 finally + CORE 워치독이다
- 보드 정지 버튼은 되돌릴 수 없는 조작이다 (concept 16 Law 3). 새 CORE 색을
  import하지 않는다

**Alternatives:** 보드가 로봇 URL로 stop을 보내는 안은 D-101 위반이다. 스페이스를
운영자 콘솔에만 두는 안은 게임 호스트에 사람이 없다.

**Consequences:** `run_match(..., halt_check=...)`. 미리보기 보드에 정지 버튼.
pytest는 `halt_check`로 키보드를 흉내 낸다.

**Validation / Transition:** `test_session.py`, `test_preview.py`. DEVICE/FIELD PARKED.

**References:** D-90, D-96, D-101, D-102, SAF-001.

---
