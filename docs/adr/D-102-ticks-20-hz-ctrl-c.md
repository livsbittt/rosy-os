## D-102 노트북 매치 루프는 `--ticks`가 없으면 20 Hz로 Ctrl+C까지다

**Status:** Accepted (2026-09-18). 호스트 루프 계약이다. DEVICE GO가 아니다.

**Context:** 설계 §8은 호스트 teleop를 20 Hz로 적는다. D-101 미리보기는
`--ticks`가 없을 때만 그 루프를 열었고, `--observer overhead`만 켜면 1틱 뒤에
프로세스가 죽었다. D-96 계단 1–5는 보드가 있든 없든 관측·teleop가 유지돼야 한다.
`--preview`가 루프 수명을 겸하면 화면 없는 현장 계단이 다시 1틱이 된다.

**Decision:**

- `--dry-run`이 아니고 `--ticks`가 없으면 매치 루프는 **20 Hz** (`period_s=0.05`)로
  Ctrl+C까지 돈다
- `--ticks N`은 유한 시험·스크립트용이다. 이때는 sleep 하지 않아도 된다
- `--preview`는 보드를 켤 뿐 루프를 열거나 닫지 않는다
- 기본 observer는 여전히 `hold`다 (D-95). 루프가 길어진다고 카메라를 열지 않는다
- Ctrl+C는 traceback 없이 `halt()`한다 (이미 `run_match` finally)

**Alternatives:** 미리보기만 길게 두는 안은 계단 2 이후 보드 없이 달리기를 막는다.
기본을 1틱으로 두는 안은 현장 CLI가 시험 CLI와 같아진다.

**Consequences:** `rosy_games match --config … --observer overhead`는 `--preview`
없이도 천장 관측을 유지한다. pytest는 `--ticks`를 명시한다.

**Validation / Transition:** `src/rosy_games/test/test_cli.py`,
`test_session.py`. DEVICE/FIELD PARKED.

**References:** D-90, D-95, D-96, D-101,
[game host 설계 §8](../plans/2026-09-17-robot-soccer-game-host-design.md).

---
