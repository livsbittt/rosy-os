## D-99 학습된 축구 정책은 Policy 플러그인이며 cmd_vel을 내지 않는다

**Status:** Accepted (2026-09-18). 아직 구현하지 않는다.

**Context:** 개념 11은 AI가 액추에이터 루프를 직접 돌리지 않는다고 했다. 축구 RL이
`/cmd_vel`을 내면 D-2를 게임으로 우회한다.

**Decision:**

- `NeuralPolicy`는 `Policy.act(obs, state) -> dict[str, Twist]`만 구현한다
- 호스트 `gate`와 CORE teleop/CMD-001이 그대로 자른다
- 1단계 `MatchState`에 `reward`를 넣지 않는다. 보상은 학습 env가 `step` 결과에서
  계산한다
- `catalog`에 이름을 등록하기 전에는 파일을 만들지 않는다

**Alternatives:** 학습 루프가 모터를 직접 쓰는 안은 개념 11·D-38 위반이다.

**Consequences:** 휴리스틱과 신경망이 같은 구멍이다. D-98 Isaac env가 이 플러그인을
끼운다.

**Validation / Transition:** `POLICIES`에 `heuristic`만 있다.
`src/rosy_games/rosy_games/catalog.py`.

**References:** D-2, D-38, D-90, D-98, [concept 11](../concept/11_ROSY_AI_and_Physical_AI.md).

**Amendment (2026-09-18):** `neural` 이름은 D-109가 카탈로그에서 거절한다. 파일은
등록 전에 만들지 않는다.

---
