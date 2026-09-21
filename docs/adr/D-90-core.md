## D-90 축구는 게임 호스트이지 CORE 모드가 아니다

**Status:** Accepted (2026-09-17). 방향 결정이다. 현장 1v1 GO가 아니다.

**Context:** Pinky 두 대로 차체 푸시볼 1v1을 하고 싶다. CORE에 `SOCCER` 모드를
넣으면 게임 규칙·공 좌표·두 대 중재가 로봇 안에 들어가고, 최종 `cmd_vel`과
OpenCV가 다시 CORE 이미지로 돌아온다 (D-38, D-66). 앞 카메라는 320×240 장애물용이지
공 추적이 아니다.

**Decision:** 축구는 기존 `IDLE`/`MANUAL`/`NAVIGATION`/`DOCKING`/`EMERGENCY` 위에
얹는 **노트북 게임 호스트**다.

- `RobotMode.SOCCER` 없음. CORE는 게임을 import하지 않는다
- 1단계는 천장 카메라 + 호스트가 양쪽 CORE teleop (`MANUAL`, SAF-002 워치독)
- 호스트는 최종 `cmd_vel`을 발행하지 않는다
- 코드는 `src/rosy_games`에 산다. `rosy-core`/`rosy-io`에 OpenCV를 넣지 않는다
- DEVICE/FIELD HOLD인 동안 서로 박는 속도의 경기를 GO로 적지 않는다
- 온보드 시야(2단계)는 1단계가 여러 번 반복되기 전에 열지 않는다

설계 본문: [robot soccer game host](../plans/2026-09-17-robot-soccer-game-host-design.md).

**Amendment (2026-09-17):** 경기의 집은 `rosy_games`다. Fleet은 로봇 통로(명단·토큰·일괄
stop)이고 Isaac은 나중에 붙는 시뮬/학습 어댑터다. 축구를 `rosy_fleet` 안에 넣지 않고,
D-62 카탈로그에도 올리지 않는다. `game` 모듈은 `cv2`/Isaac을 모른다. 시작 경로
`tools/soccer/`는 이 패키지 트리로 대체한다. 심판을 Fleet 서버로 “옮긴다”는 문장은
매치 시작 버튼의 자리이지, 규칙 엔진의 이사가 아니다.

**Alternatives:** CORE 모드로 넣는 안은 미들웨어를 게임으로 만든다. Nav2로 공을
쫓는 안은 공을 장애물로 만들고 너무 느리다. Fleet 안에 넣는 안은 관제 패키지가
규칙·RL·Isaac 의존을 떠안는다. Isaac이 경기를 소유하는 안은 학습에는 유리하고
Isaac 없는 실기 1v1을 늦춘다.

**Consequences:** 1단계 실패는 호스트 정책 문제이지 CORE 계약 위반이 아니다.
Fleet 콘솔은 매치를 켤 수 있다. `reset()`은 `rosy_games`가 한다 (D-12, D-88).

**Validation / Transition:** `RobotMode`에 `SOCCER`가 없다.
`src/rosy_core/test/test_protocol_schemas.py`. 구현은 별도.

**References:** D-1, D-2, D-12, D-33, D-38, D-59, D-62, D-66, D-88.

---
