# Fleet 콘솔 ↔ 신호등 컨트롤러 연동 설계 (G-S3)

- **Status:** Draft — 구현 전 설계. 실행 계획(태스크 분해)은 승인 후 별도 파일로
- **Date:** 2026-09-21
- **Related:** `signal/README.md` (ROSY-SIGNAL-001 — 장치 계약, 이미 구현됨),
  `docs/plans/2026-09-21-traffic-light-controller-research.md` (조사 보고서),
  `docs/plans/2026-09-14-site-middleware-role-fabric-design.md` (D-59),
  `src/site/fleet/fleet/server/AGENTS.md`

## 1. 목적

Fleet 콘솔(관제)이 사이트 신호등 컨트롤러(ROSY-SIGNAL-001)를 **모으고(gather) 흩뿌린다
(scatter)** — D-59 site fabric 의 또 하나의 디바이스일 뿐이다. 로봇이 추가되지
않고, ROS 가 추가되지 않고, `site/` 계층의 "ROS import 금지"도 유지된다.

장치 쪽 페일세이프(부팅·감독자 침묵 → 적색 점멸)는 **장치가 소유한다**. 이 설계가
하는 일은 그 위에 (a) 상태 수집, (b) 명령 하달, (c) 의도 재단언, (d) e-stop 연동,
(e) 관제 화면이다.

## 2. 원칙 (어긋나면 설계를 고친다)

1. **명령 주체는 Fleet 콘솔 하나다.** 로봇 CORE 는 신호등을 모른다. 장치 보고
   (`/status`)는 표시·대조용이지 로봇 안전 판단의 입력이 아니다.
2. **신호등은 안전 인터록이 아니라 표시 장치다.** 교행 순서 판정은 여전히
   `traffic.py` 가 하고(D-12), v1 에서 신호등은 그 판정의 *표현*이지 입력이 아니다.
   `traffic.py` 를 고치지 않는다.
3. **장치의 실패 표시를 믿고, 되살리지 않는다.** `mode=failsafe` 를 보면 관제는
   마지막 의도를 새 `seq` 로 재단언한다. 장치가 스스로 옛 명령을 복원하는 경로는
   없다(장치 계약이 NVS 저장을 금지한다).
4. **부분 실패는 200 이고 본문에 담긴다.** e-stop 이 그렇듯(`estop_all`), 신호등
   scatter 도 어느 기가 받았는지 본문으로 남긴다. 5xx 로 접으면 화면이 모른다.
5. **고장 격리.** 신호등 폴링 실패가 로봇 gather 를 지연시키지 않는다. 독립
   태스크, 짧은 타임아웃, 실패는 상태 필드로만.

## 3. 구성

### 3.1 `signals.yaml` — 장치 목록과 토큰

robots.yaml 과 같은 모양, 다른 계약:

```yaml
signals:
  - signal_id: "signal_1"
    base_url: "http://10.10.1.51"   # 끝 슬래시 없음
    token: "operator-token-for-signal-1"
```

- 검증 규칙은 `swarm/robots.py` 의 그것을 따른다: 필수 키, **따옴표 문자열 강제**
  (YAML 1.1 함정 — 8진·`yes` 문제), 스킴 검사, 중복 id 거절, 쓰기는 0600.
- robots.yaml 에 섞지 않는다. `robots` 리스트 검증이 `robot_id` 를 요구하므로
  억지로 섞으면 두 계약이 서로의 스키마를 끌어안게 된다.
- 새 모듈 `fleet/server/signals.py` 에 `SignalEndpoint` + `load_signals()` 로
  둔다. `swarm/` 이 아니다 — `swarm` 은 로봇 계약 전용이고(transport.py 가 "로봇
  계약을 부르는 유일한 모듈"), 신호등은 다른 계약이므로 그 경계를 건드리지 않는다.

### 3.2 `fleet/server/signals.py` — 클라이언트와 콘솔

```
SignalEndpoint           # signal_id / base_url / token (frozen dataclass)
SignalClient (Protocol)  # 테스트를 위한 가짜 경계
HttpSignalClient         # httpx. GET /status, POST /command — X-Rosy-Token 헤더
SignalConsole            # 상태 캐시 + 의도 기억 + 폴링 루프 + scatter
```

`SignalConsole` 책임:

- **폴링 루프:** 장치마다 ~2 s 간격 `GET /status` (토큰 필수 — 토큰 없는 GET 은
  하트비트로 안 섞는다는 장치 계약 때문). 성공하면 `last_status` 갱신.
- **의도 기억:** 운영자가 내린 마지막 명령(lamps/mode)을 콘솔이 기억한다.
  `mode=failsafe` 를 보면 **같은 의도를 `seq`+1 로 재단언**한다. 재단언은 1회
  시도 후 재폴링 — 스톰을 만들지 않는다. `409 stale_seq` 가 연속되면 그 장치를
  "명령 불일치"로 표시하고 운영자 손을 기다린다(자동 재시도 상한 1).
- **명령 하달:** `command(signal_id, mode, lamps=None, cycle=None)` — 장치에 POST,
  결과(200/403/400/409/타임아웃)를 그대로 돌려준다.
- **all_red scatter:** 등록된 전 기기에 `all_red` 를 병렬로. 부분 실패를 본문에
  담아 돌려준다(원칙 4).

### 3.3 FleetConsole / app.py 통합

- `FleetConsole.__init__` 이 `SignalConsole` 을 옵션으로 받는다(신호등 없는
  사이트도 같은 서버로 뜬다 — signals.yaml 이 없으면 signals 기능은 비어 있는 채).
- `snapshot()` 은 `"signals"` 키를 추가한다: `{signal_id: {mode, lamps, faults,
  secs_since_contact, online}}`. 폴링 루프의 캐시를 읽는 것이지 폴링을 기다리지
  않는다 — UI 의 한 번의 poll(`/api/fleet/state`)로 로봇과 신호등이 함께 그려진다.
- 새 엔드포인트:

| 경로 | 뜻 |
|---|---|
| `GET /api/fleet/signals` | 신호별 상세 상태 |
| `POST /api/fleet/signals/{id}/command` | 수동 명령 (mode, lamps, cycle) |
| `POST /api/fleet/signals/{id}/release` | `manual` 녹색 해제 등 운영자 의도 — 같은 command 의 얇은 별칭 (v1 생략 가능) |

- `POST /api/fleet/estop` 는 기존 로봇 정지에 **신호등 `all_red` scatter 를
  병렬로 추가**한다. 순서 논쟁(로봇 먼저? 신호 먼저?)은 하지 않는다 — 병렬이고
  둘 다 본문에 남는다. 신호등이 죽어도 e-stop 은 200 이다.
- 인증: 기존 `guard`(콘솔 토큰)를 그대로 통과한다. 장치 토큰(`X-Rosy-Token`)은
  서버 내부에서 붙이고 화면에는 노출하지 않는다.

### 3.4 관제 UI (`server/web/`)

- 신호등 카드: `signal_id`, mode 배지(`failsafe` 는 눈에 띄는 경고색), 램프 도트
  3개(구동값 `lamps`), `faults` 목록, `secs_since_contact`.
- 명령 버튼: 녹색/황색/적색 지정(manual), 전체 적색(all_red), 점멸(flash_red),
  사이클(cycle, 값은 프리셋). v1 에 자유 cycle 수치 입력은 없다.
- **CSP `style-src 'self'` — 인라인 스타일 금지, 색·배치는 클래스로만** (server
  계층 기존 규칙 준수).
- `failsafe` 카드는 "재단언 대기/명령 불일치" 상태를 함께 보여준다 — 운영자가
  "왜 신호가 내 말을 안 듣나"를 화면에서 판별하게.

## 4. 안전 검토

- **장치 침묵 → 적색 점멸은 장치가 한다.** Fleet 이 죽어도 신호등은 스스로 실패
  표시로 간다. Fleet 은 살아나서 재단언할 뿐이다. 이 설계에 "신호등 상태 유지를
  위한 장치 측 저장"을 추가하지 않는다.
- **재단언 루프와 409:** 콘솔의 `seq` 와 장치의 `last_seq` 는 재부팅에서 어긋날 수
  있다. 재단언은 실패를 두 번 겪으면 멈춘다 — 화면에 "명령 불일치"로 남기고 운영자
  개입(새 명령)을 기다린다. 무한 재시도는 스톰이고, 스톰은 다른 장치의 폴링 예산을
  잡아먹는다.
- **폴링 예산:** 신호등 N 기 × 2 s 는 httpx 커넥션 풀에서 로봇 폴링과 분리된 풀을
  쓴다. 신호등 10기가 늘어도 로봇 상태 지연이 커지지 않게.
- **토큰 취급:** `signals.yaml` 은 robots.yaml 과 같은 등급의 비밀 파일이다
  (0600, 리포지토리 커밋 금지는 배포 규칙을 따른다). 서버 로그에 토큰/헤더를
  남기지 않는다.

## 5. 테스트 계획 (네트워크 없이)

- `SignalClient` 가짜(`test/fakes.py` 확장 또는 `test/fake_signals.py`): 상태
  기계를 가진 가짜 장치 — `failsafe` 진입, `409 stale_seq`, `403` 재현.
- `SignalConsole` 단위: 의도 재단언(1회 한계), all_red scatter 부분 실패 본문,
  폴링 실패가 캐시를 오염시키지 않음. `settle()` 스타일 폴링, wall-clock sleep 금지
  (계층 기존 규칙).
- `app.py`: `/api/fleet/state` 의 `signals` 키, 신호 엔드포인트의 guard/401,
  e-stop 본문에 signals 결과 포함 — `fastapi.testclient`.
- **계약 시험 확장(G-S3 착수 시):** `test/test_signal_contract.py` 에 README JSON
  ↔ `HttpSignalClient` 파서 대조를 추가한다(dock 의 `test_dock_contract.py` ↔
  `DockAgent._parse` 선례). 이 파일은 signal 모듈 소유라 그 쪽 작업과 조율해서
  건드린다.
- `python -m flake8 src/site/fleet --max-line-length=120` — 계층 기본.

## 6. 작업 분해 예고 (실행 계획으로 옮길 것)

| # | 작업 | 검증 |
|---|---|---|
| T-S3-1 | `signals.py`: `SignalEndpoint` + `load_signals()` (robots 규칙 재사용) | 단위 — 나쁜 YAML 전부 거절 |
| T-S3-2 | `HttpSignalClient` + `SignalClient` Protocol + 가짜 | 파서 대조(계약 시험 확장) |
| T-S3-3 | `SignalConsole`: 폴링 루프·의도 재단언·scatter | 가짜로 settle 테스트 |
| T-S3-4 | `FleetConsole`/`app.py` 통합: snapshot `signals`, 신호 엔드포인트, e-stop 병렬 scatter | testclient |
| T-S3-5 | 관제 UI 신호등 카드 + 명령 버튼 | CSP 준수, 브라우저 옵트인 시험 |
| T-S3-6 | CLI: `fleet console` 이 signals.yaml 받기 | 기존 CLI 시험 확장 |

## 7. 열린 질문

1. `release` 별칭 엔드포인트를 v1 에 넣을지 — command 하나로 충분한지.
2. e-stop 시 신호등 `all_red` vs `flash_red` — "명령된 정지"(점등)가 현재 계약의
   정의와 맞다. 유지하는 걸 기본으로.
3. `traffic.py` 교행 판정이 신호등 패턴을 건드릴 시점 — v1 밖. 판정 결과를 표시로
   내보내는 것(예: 대기열 해제 시 녹색)은 별도 설계로.
4. signals.yaml 위치 — `deploy/robot/config` 계열과 나란히 둘지, 관제 PC 쪽 설정
   루트를 새로 둘지. 배포 담당과 확인.
