# Fleet 릴레이 준비 신호 실측화 실행 계획 — D-134 이행

- 작성: 2026-09-20. 근거 ADR: D-134(Proposed). 선행: D-132(순서 뒤집기 — 작업 트리 미커밋)
- 원칙: **준비 신호는 실측으로 말한다.** 소켓 열림이 아니라 데이터 흐름을 증명한다.
  검증은 호스트 pytest 적색-녹색 — DEVICE/FIELD 주장 금지(D-91)

## 0. 결함 장부 (리뷰 실측)

| 위치 | 현상 | 위험 | 태스크 |
|---|---|---|---|
| `swarm/relay.py:194` | `_leader_connected=True`를 `pose_stream()` 시도 전에 세움. async generator라 첫 `__anext__` 전까지 접속 없음 — 리더 down이어도 찰나 참 가능 | 검증 안 된 리더에 무장 (거짓 양성) | T1 |
| `swarm/relay.py:131` `stop()` | lane만 `connected=False`, 리더 flag 잔류. Cancel 사망 경로도 동일 | stop 후 `streams_ready()` 옛 값 유지 | T2 |
| `swarm/session.py:155` | `self.relay` 대입이 `streams_ready()` 확인 전. timeout 시 stopped 릴레이 잔류 | `_log_hold:515`의 `is None` 판단 어긋남 | T3a |
| `swarm/session.py:161` | `except SessionError:`에서 reason 고정 `"relay_failed:streams did not open"` | factory 원원인 마스킹 | T3b |
| `swarm/session.py:156` polling | 60회(3 s) 동안 `STOPPED` 미감시. 대기 중 `stop()`이 와도 3 s 소진 후 `_arm`까지 갔다가 복귀 | 중단 지연 + 이중 stop/disarm | T3c |

## T1 리더 flag 실측화

- `_read_leader` loop-top `self._leader_connected = True` 제거
- 첫 프레임 수신 시(`got_frame=True` 뒤 — `_on_frame` 첫 호출 지점)에 세움
- `streams_ready()` 정의는 그대로: 리더 실측 AND 전 팔로워 sink 개방
- 소유: `swarm/relay.py`. 증거: T4a 적색-녹색

## T2 stop 리셋

- `stop()` 끝에 `self._leader_connected = False` 한 줄 (lane 리셋 옆)
- 취소로 `_read_leader`가 죽는 경로도 이 한 줄로 커버 — 별도 핸들러 없음
- 소유: `swarm/relay.py`. 증거: T4b

## T3 `_open_relay` 3점

- **T3a 확인 후 대입**: `self.relay = relay`를 `streams_ready()` 확인 뒤로 이동.
  실패 시 `self.relay`는 `None` 유지 (멱등 `_stop_relay` 동작은 그대로)
- **T3b 원인 보존**: `except SessionError:`에서 `reason = (f"relay_failed:{exc}", None)`.
  고정 문자열 폐기 — 현재 테스트는 `startswith("relay_failed")`만 봐서 둘 다 통과하므로
  T4c가 원문 보존을 직접 단언해야 함
- **T3c 중단 감시**: polling loop 안에 `if self.state is SessionState.STOPPED:`
  체크 — 대기 중 stop이면 즉시 탈출 (이미 무장된 팔로워는 없으므로 relay.stop()만)
- 소유: `swarm/session.py`. 증거: T4c·T4d

## T4 검증 (적색-녹색 4건 + 회귀)

- **T4a** 프레임 없는 리더는 `streams_ready()` 거짓 — `pose_stream()`이 즉시 끝나거나
  예외를 던지는 fake로, 팔로워 sink는 열린 상태. 적색: 현재 loop-top 대입이면 찰나 참
- **T4b** stop 후 거짓 — 정상 기동 → `stop()` → `streams_ready()` 거짓 단언
- **T4c** factory `SessionError("cannot build ...")` 원문 보존 — `s.reason[0]`에
  원문 포함 단언 (현재 고정 문자열이면 적색)
- **T4d** open 대기 중 stop 즉시 탈출 — `streams_ready()` 거짓인 relay + 주입 `sleep`으로
  대기 중 `stop()` 호출, 3 s 소진 전에 `STOPPED` + follow 무접촉 단언
- 회귀: `python -m pytest src/site/fleet/test/test_session.py src/site/fleet/test/test_server_formation.py src/site/fleet/test/test_relay.py -q` — 94 passed 유지
- ROS-SIM은 D-132 계승: 무장 직후 `follower_tx ≥ 1` 실측 (이 계획의 범위 밖)

## 순서·종료 조건

- T1 → T2 → T3a·b·c → T4a·b·c·d → 회귀. T1 없이 T4a는 적색 그대로다
- 종료: 4건 녹색 + 회귀 94 passed + D-134 Status → Accepted + fleet `logs.md` 항목
- 범위 밖: ROS-SIM 재실행, D-133 SIGSEGV 추적, D-131 2·3단계 — 각자 ADR 소유
