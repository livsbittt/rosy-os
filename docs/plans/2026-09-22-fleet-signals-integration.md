# Fleet 콘솔 ↔ 신호등 연동 실행 계획 (G-S3)

- **Status:** 구현·호스트 검증 완료 (2026-09-22). 물리 신호등 DEVICE 검증은 별도 HOLD
- **Design:** `2026-09-21-fleet-signals-integration-design.md`
- **Contract:** `signal/README.md` (ROSY-SIGNAL-001)

설계에서 바뀐 것 하나: **상시 폴링 루프 대신 요청 시 갱신(throttled refresh)**.
`snapshot()` 이 신호등 캐시를 갱신(주기 제한 2 s)하고 UI 가 계속 `/api/fleet/state` 를
당기므로 별도 백그라운드 태스크가 없다. 관제가 보지 않으면 장치는 스스로 페일세이프로
간다 — 그것이 장치 계약의 뜻이기도 하다. 태스크 수명 관리·wall-clock sleep 도 없어진다.

| # | 작업 | 시험 |
|---|---|---|
| T-S3-1 | `fleet/server/signals.py`: `SignalEndpoint`, `load_signals`/`write_signals` (robots 규칙 재사용: 따옴표 강제·스킴·중복·0600) | `test_server_signals.py::test_loader_*` |
| T-S3-2 | `SignalStatus` 파서 + `HttpSignalClient` (`X-Rosy-Token`) + `SignalClient` Protocol | `test_parser_*`, `test_http_client_*` |
| T-S3-3 | `SignalConsole`: 캐시·의도 기억·재단언(1회 한계)·`all_red` scatter·throttled refresh | `test_console_*` |
| T-S3-4 | `FleetConsole` 통합(snapshot `signals` 키, e-stop 병렬 scatter) + `app.py` 엔드포인트 | `test_app_*` |
| T-S3-5 | 관제 UI 신호등 카드(클래스만, CSP 준수) | 수동/브라우저 옵트인 |
| T-S3-6 | CLI `fleet console --signals signals.yaml` | `test_cli_signals` |

시험은 전부 `src/site/fleet/test/` 에서 가짜 클라이언트로 — 네트워크·sleep 없음
(`fake_signals.py` 신설). 파서 대조(README JSON ↔ 클라이언트)는 signal 모듈 소유인
`test/test_signal_contract.py` 와의 조율이 필요해 이 슬라이스 밖으로 남긴다.
