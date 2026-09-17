# D-72 인터페이스 원칙 이행 설계

작성일: 2026-09-17
상태: **pending approval** — 실행 승인 전. 이 문서는 아직 어느 모듈의 `progress.md`에도 등록하지 않았다.

관련: [D-72](../reference/ROSY%20ADR%20Log.md) (Accepted) · [D-77](../reference/ROSY%20ADR%20Log.md) · [concept 16](../concept/16_ROSY_Interface_Design_Principles.md) ·
D-7, D-11, D-18, D-23, D-32, D-55, D-61, D-68, D-71, D-73 ·
[device validation 계획](2026-09-13-rosy-os-device-validation-implementation-plan.md) G4

RALPLAN 합의 루프 2회(Planner→Architect→Critic→Planner→Architect) 결과다. §11에 루프 상태와 미검토 부분을 적는다.

---

## 1. 기준선 (실측 2026-09-17)

| 항목 | 원본 | gzip -9 |
|---|---|---|
| `rosy_core` 서빙 자산 7개 | **122,188 B** | **29,146 B** |
| `rosy_control/web/dashboard.html` | 102,319 B | 29,572 B |
| 합계 | 224,507 B | **58,718 B** |

내역: app.js 31,712 / styles.css 28,864 / index.html 27,533 / settings.js 19,470 / map.js 9,160 / dom.js 3,327 / client.js 2,122.
`AGENTS.md`(2,499 B)와 `__init__.py`는 allowlist 밖(`api/app.py:45-52`)이라 서빙되지 않는다.

측정 명령:
```
cd src/rosy_core/rosy_core/web
cat index.html styles.css app.js map.js dom.js client.js settings.js | wc -c
cat index.html styles.css app.js map.js dom.js client.js settings.js | gzip -9 -c | wc -c
```

빌드 도구 없음(`package.json`/vite 없음). CSP는 `style-src 'self'; script-src 'self'`(`api/app.py:88-92`)라 인라인 금지 — 새 CSS는 링크 파일이어야 한다.

**모든 수치는 바이트로만 쓴다.** KB 표기는 1000/1024 모호성 때문에 쓰지 않는다.

---

## 2. 원칙과 제약

**선택 원칙** (옵션을 가르는 것만)

1. **법은 계약 시험으로만 산다.** 시험 없는 법칙은 주석이고 D-72는 Proposed에 머문다.
2. **되돌릴 수 있는 순서로.** 거버넌스 기록 변경은 구현 가능성이 증명된 뒤에 온다.

**제약** (모든 옵션 공통, 선택 근거 아님)

- G4를 새 일로 만들지 않는다 — 증거 상태 작업은 device-validation 게이트 G4의 이행이다.
- 번들러·npm·외부 CDN·웹폰트·별도 프론트엔드 런타임 금지(D-23).
- ROS 무의존 조각을 먼저.

## 3. Decision Drivers

1. G4가 기한을 준다 — 값별 신선도 표시 + 낡은 값의 위험 동작 차단.
2. Pi 5 / 오프라인 / 번들러 없음.
3. D-72를 Accepted로 올리려면 계약 시험이 필요하다.

드라이버 1은 A와 C가 모두 만족한다. A를 고르는 근거는 선택 원칙 1·2뿐이며, **S5·S6을 빼면 그대로 Option C가 된다**(§4).

## 4. Options

| | 내용 | 판정 |
|---|---|---|
| **A** | 전 단계 실행, 콘솔 통합만 보류 | **확정 (2026-09-17, 사용자 결정)** |
| **B** | 콘솔 통합 우선 | 기각 — CSP·자족성 미결에 의존, device validation과 경쟁, 비가역이 먼저 |
| **C** | S0~S4 + 가장 싼 계약 시험 둘, S5·S6 제외 | **정당한 축소판.** 범위를 줄이려면 이것 |
| **D** | S3·S4를 device-validation 계획으로 편입 | **부분 채택** — 실행은 이 계획, G4 증거 기록은 device-validation 계획으로 단일화(§9) |

A의 단점을 명시한다: 콘솔 통합 전까지 두 대시보드가 공존하며 **"이 로봇 괜찮나"에 답이 둘로 남는다. 이 계획은 그 문제를 풀지 않는다.**

## 5. 어휘 — 명시적 사상표

concept 16 §5와 G4가 다른 이름을 쓴다. G4가 선행 계약이므로 G4 어휘를 채택하되 네 상태를 하나도 잃지 않는다.

| concept 16 §5 | 확정 어휘 | 의미 | 범위 |
|---|---|---|---|
| `live` | `fresh` | 현재 값, 출처 있음 | 값별 |
| `stale` | `delayed` | 값은 있으나 낡음 | 값별 |
| `absent` | `disconnected` | 출처는 있는데 수신이 끊김 | **값별**, 전송 계층 아님 |
| `unavailable` | `unavailable` | 이 장비에 해당 출처가 없음 | 값별 |

WebSocket 단절은 페이지 수준 별개 표시이며 이 어휘를 쓰지 않는다.

**알려진 중첩(해소하지 않고 기록한다):** concept 16 §5의 `unavailable`("this device has no such source")과 §8 capability의 `absent`("not provided by this device")는 **같은 사실을 말한다**. §8 쪽을 `not_provided`로 개명해 토큰 충돌만 없애고, 의미 중첩은 남는다. S4 이후 "이 로봇에 라이다가 없다"는 사실이 두 렌더러(`/system/capabilities` ↔ `/system/inventory`)에서 각각 그려진다. S8(콘솔 통합) 전까지 단일화하지 않는다.

G4는 렌더링만이 아니라 **동작**도 요구한다 — "stale values disable hazardous actions". 증거 상태는 표시 속성이 아니라 명령 게이트다.

---

## 6. 단계

각 단계는 하네스 규약을 따른다: 변경 → `logs.md` append → 게이트 이동 시 `progress.md` overwrite → `python tools/harness/rosy_harness.py generate`.

### S0 — 응답 압축 (가장 싸고 가장 큰 경량화)

사용자 제약 "웹은 최대한 가볍게"에 대한 실제 답이다. `rosy_core/api/`에 압축 미들웨어가 **하나도 없다**(grep 0건). `app.py:83,101`은 원본 `FileResponse`를 보낸다.

- `api/app.py`에 `GZipMiddleware` 추가. **import 1줄 + `add_middleware` 1줄.** 새 의존성 없음, 번들러 없음, D-23 준수
- 효과(실측): core 122,188 → **29,146 B**. 첫 로드에서 **93,042 B** 감소
- 나머지 전 단계의 소스 증감 합(+2,500 B 최악)의 **37배**다. 이 한 줄이 먼저다
- 바이트: 소스 +~100 B, 전송 −93,042 B
- 게이트: `rosy_core` LOCAL — evidence: 압축 응답 단언 시험(`Content-Encoding: gzip`) + 기존 무회귀 / cmd: `PYTHONPATH=src/rosy_core:src python3 -m pytest src/rosy_core/test -q`

### S1 — `tokens.css` + 색 집합 계약 (rosy_core 단독)

- `src/rosy_core/rosy_core/web/tokens.css` 신규: categorical / status / neutral 3집합, 증거 4상태, surface 위계
- **"원시 색"의 정의를 시험에 명시한다.** `styles.css`에는 hex 25개(19종) **외에 `rgba()`/`hsl()` 37개**가 있다. 구조색(`--border: rgba(255,255,255,0.10)`)까지 포함하면 치환은 62곳이다. 시험은 **전부 포함**하되 알파 변형은 토큰에서 파생하도록 허용한다 — 면제 형태를 산문이 아니라 시험 본문에 적는다
- `api/app.py:45-52` allowlist에 `tokens.css` **한 줄 추가**. 디렉터리 스캔 전환은 **금지** — `{asset_name:path}`가 슬래시를 허용하므로(`app.py:96-105`) allowlist가 유일한 경로 순회 방어다
- 시험(D-73 준수): `src/rosy_core/test/test_ui_token_contracts.py`, **rosy_core 파일만 단언**
  - 토큰 파일 밖 원시 색 → 실패
  - status 색이 categorical 위치에 → 실패. **현행 위반을 잡는다: `map.js:47`의 `[196,219,118]`과 `map.js:162`의 pose 마커가 둘 다 `#c4db76`(= `--signal-lime`)다.** 이 단계에서 두 자리를 분리한다(시각 변경 1건, 명시적)
- 바이트: 62곳 치환 기준 **≤ +2,400 B** (tokens.css 신규 ~1,200 B 포함)
- 게이트: `rosy_core` LOCAL — cmd 위와 동일

### S2 — 맵 래스터 색 계약 + 불일치 해소 (rosy_control 단독)

`render_png`에는 색 값이 없다(docstring뿐, `web_node.py:220-222`). 실제 값은 `sensing/map_raster.py:8-10`의 **BGR** 튜플이다.

- `map_raster.py`에 모듈 상수 도입: `OCCUPANCY_BGR = {"unknown": (22,22,21), "free": (35,35,34), "wall": (225,224,217)}`
- 시험(D-73 준수): `src/rosy_control/test/`, `test_map_raster.py` 옆. **rosy_control 파일만 단언**. `map_raster.py`를 import하면 numpy 의존이 따라오고 CI 의존 목록에 numpy가 없으므로 **텍스트 파싱**으로 쓴다
- 계약: `dashboard.html:13,17`(및 JS 사본 `:585`)의 토큰이 `OCCUPANCY_BGR`의 **BGR→RGB 역순**과 일치
- **불일치는 한 값이 아니라 세 값이다**(실측):

  | | BGR | 실제 PNG | `dashboard.html` 토큰 |
  |---|---|---|---|
  | unknown | (22,22,21) | `#151616` | `#161615` |
  | free | (35,35,34) | `#222323` | `#232322` |
  | wall | (225,224,217) | **`#d9e0e1`** | **`#e1e0d9`** |

  unknown·free는 1/255라 육안 무해하지만 계약은 셋 다 깨진다. wall은 지도 최대 면적이고 따뜻/차가움이 뒤집힌다. **어느 쪽이 정답인지 정하는 것이 이 단계의 산출물이며 값 변경이다.** PNG를 실제로 굽고 캔버스와 나란히 놓고 정한다
- **기존 시험도 범위다**: `src/rosy_control/test/test_map_raster.py:12,13,14,20,21`이 세 튜플을 5곳에 하드코딩한다. "서버가 틀렸다"로 결론나면 함께 바뀐다
- **범위 경계:** `rosy_core/web/map.js`는 이 계약 **밖**이다. core는 `/api/v1/map`에서 클라이언트가 직접 래스터를 그리고(4버킷, 임계 20/60), control은 `/map.png`를 서버가 굽는다(3버킷, 임계 65) — **별개 파이프라인이다.** concept 16 §6의 래스터 계약은 `dashboard.html ↔ map_raster.py`만 구속하고, `map.js`는 색 집합 법(S1)만 적용받는다. 이 문장을 concept 16 §6에 추가한다(S7)
- 바이트: rosy_core 서빙 자산 변화 0
- 게이트: `rosy_control` LOCAL — cmd: `PYTHONPATH=src/rosy_control:src python3 -m pytest src/rosy_control/test -q`

### S3 — 서버: 값별 신선도 **판정** (신규 단계)

실측: `protocol/schemas.py:256-274`의 `StateSnapshot`은 envelope `timestamp` 하나뿐이고 `api/`에 `received_at` 참조가 0개다. 값별 `received_at`은 `bridge/translate.py:76-129`까지만 있고 API로 나오지 않는다.

**중요:** 타임스탬프만 내보내면 안 된다. 클라이언트가 `fresh`/`delayed`를 만들려면 임계값이 필요한데, `navigation/readiness.py:118`의 `stale_after_s`와 `safety/manager.py:214`의 작동 예산(`.2 s`)은 **직렬화가 0건**이다. 타임스탬프만 주면 클라이언트가 임계값을 하드코딩하게 되고, 그건 §5가 금지한 "두 번째 판정자"다.

- `StateSnapshot`에 값별로 **`{received_at, evidence}`를 additive 추가**. `evidence`는 서버가 계산한 `fresh`/`delayed`/`disconnected`/`unavailable`이다. 그 판정을 낳은 임계값도 함께 노출한다
- 판정의 출처는 기존 서버 권위다: `navigation/readiness.py:118,127`(`missing_or_stale:`), `safety/manager.py:211`(`actuation_stale_or_over_budget`), D-23("속도 표본 500 ms 만료")
- **D-18 동반 수정 필수**: `protocol/schemas.py` + `docs/reference/ROSY API & Protocol Reference.md`
- **버전 둘을 구분해서 올린다**: `schemas.py:22`의 `PROTOCOL_VERSION`("1.0")과 API Ref 문서 버전(현재 v1.7, `ROSY API & Protocol Reference.md:5`)은 다른 번호다. D-31/D-32가 올린 것은 문서 쪽이다. PRT-006 분류는 additive이므로 MINOR
- Fleet/WS 소비자 영향 확인 — `StateSnapshot`은 `/ws/state` payload와 동일(`schemas.py:257`)
- API Ref는 git 클린이므로 이 단계는 더러운 ADR Log를 건드리지 않는다
- 게이트: `rosy_core` LOCAL

### S4 — 클라이언트 증거 상태 + 위험 동작 게이트 = G4 이행

- `dom.js`: `setText(id, value, fallback)` → 증거 상태를 실은 바인딩. 렌더링은 CSS 속성 선택자(`[data-evidence]`)로, JS 분기 없이
- **클라이언트는 서버의 `evidence` 문자열을 그대로 표시한다. 임계값 산술을 클라이언트에 두지 않는다.**
- **마이그레이션 범위 명시:** `setText` 호출은 `app.js` 83곳 + `settings.js` 4곳 = **87곳**. 이 중 **텔레메트리 출처 값만** 대상이다. 호스트명·릴리스 문자열·폼 메시지 같은 정적 텍스트는 제외하며, 대상 목록을 시험에 명시해 시험이 정적 텍스트에 증거 상태를 강요하지 않게 한다
- 위험 동작 게이트: `delayed`/`disconnected` 입력에 의존하는 명령 버튼 비활성화 + 이유 표시
- 바이트: 87곳 중 대상만 치환하며 호출부마다 증가한다. v1의 "분기 제거로 감소" 추정은 철회(`dom.js:8-10`이 이미 fallback을 중앙화해 제거할 분기가 없다). 대표 1곳 실측 후 외삽. **≤ +1,500 B**
- **G4 증거는 여기서 기록하지 않는다.** device-validation 계획이 ` M`(수정 중)이므로 §9의 규칙에 따라 S7에서 쓴다
- 게이트: `rosy_core` LOCAL

### S5 — 장식 제거 + 절차 문법 (축소 시 제외)

- 삭제: `.ambient-grid`(`index.html:13`, `styles.css:41-52`), radial gradient 2겹(`styles.css:30-31`), `--shadow`, `data-tone`(`index.html:80,85,90` / `styles.css:223-224`), `.eyebrow` **12곳**, `FIELD RUNTIME / 01`, `--display: Georgia`
- 게이지: 중립 채움 + 임계에서만 status 색. 숫자에 `tabular-nums`
- host/release/commissioning 3열 그리드 → 부팅 순서 수직 열
- **기존 시험 갱신이 이 단계의 과제다**: `src/rosy_core/test/test_dashboard.py`(`WEB_ROOT.glob("*.js")`로 자산 단언), `test/test_dashboard_browser.py`(실제 DOM 구동). 후자는 루트 `test/`라 harness상 `deploy` 모듈 소유임을 유의
- 바이트: 삭제 대상 실측 **총 ~1,638 B**(CSS ~927 B + HTML ~711 B)이고, 추가되는 게이지·임계·`tabular-nums`·수직 레이아웃 규칙이 상쇄한다. **순감을 하드 게이트로 걸지 않는다**(§8). 목표는 "측정된 순감 > 0"
- 게이트: `rosy_core` LOCAL — 브라우저 증거를 쓸 경우에만 `ROSY_RUN_BROWSER_TESTS=1 python -m pytest test/test_dashboard_browser.py -q`(기본 skip이므로 명령을 명시하지 않으면 증거가 아니다)

### S6 — capability 4상태 (축소 시 제외)

- 선행 사실: `domain/capabilities.py:32-34`의 `CapabilityDescriptor`는 `id` + `available: bool` **둘뿐**이다. 불리언 하나로 4상태와 이유를 만들 수 없다
- **분기를 명시적으로 고른다: inventory descriptor를 additive 확장한다.** 상태 + 이유를 서버가 제공한다. CAP-001 본문은 손대지 않으므로 D-68 준수
- **클라이언트가 이유를 합성하는 안은 금지.** JS가 지어낸 "node down"은 D-32가 없앤 거짓 200의 반대 방향이며 concept 16 Law 0 위반이다
- 클라이언트: `app.js:275-302`의 평평한 AVAILABLE/DISABLED 덤프를 4상태 표현으로. **클라이언트는 inventory를 한 번도 호출한 적이 없다**(`/api/v1/system/inventory`는 `api/v1/system.py:165-167`에 존재) → `app.js:585` 폴링 목록에 fetch 추가
- 바이트: **≤ +900 B**
- 게이트: `rosy_core` LOCAL

### S7 — 거버넌스 정정 (마지막)

앞 단계가 어휘와 계약의 구현 가능성을 증명한 뒤에 기록을 고친다.

- `concept 16` §5를 §5 사상표로 정정(`disconnected`가 값별임 명시, capability `absent` → `not_provided`, 의미 중첩을 알려진 한계로 기록)
- `concept 16` §6에 래스터 계약 범위 문장 추가(S2의 파이프라인 경계), **그리고 `tokens.css` ↔ `dashboard.html` 교차 패키지 단언은 D-73상 합법적 거처가 없다는 한계를 기록**(§10)
- `concept 16` §11 v1 매핑에 G4 참조 추가
- ADR Log D-72 본문의 증거 4상태를 같은 어휘로 정정(Proposed이므로 본문 수정 허용), Validation에 실제 시험 경로 기입
- **device-validation 계획의 G4 행에 이 계획의 이행 결과를 기록**(S4에서 미룬 것)
- D-72 → Accepted 승격 제안(사람 승인)
- 게이트: `docs` SOURCE/LOCAL — cmd: `python tools/harness/rosy_harness.py lint` · `python -m pytest test/test_network_topology_contracts.py test/test_harness_contracts.py -q`

### S8 — 콘솔 통합

**2026-09-17 결정 (D-77):** (c) 역할 분리. 운용자 콘솔은 CORE `/dashboard`
하나. `web_node`는 레거시 런치 진단 화면이며 compose에 없다. (a) 기각.
(b) DEVICE 전까지 보류 — 두 맵 파이프라인과 `cmd_vel_raw`(D-38).

미결이었던 것: (a) CSP nonce로 단일 파일 자족성 유지 / (b) 분해해 core 자산
편입 / (c) 서버 2개 유지.

---

## 7. 경량화 지표 (바이트 상한을 대체)

v1·v2는 소스 바이트 천장을 게이트로 썼다. 그건 **잘못된 계량**이다: (i) 압축 없이 디스크 바이트를 재고, (ii) 전체 UI의 46%인 `dashboard.html` 102,319 B가 범위 밖이며, (iii) 단계별 상한의 합보다 겨우 188 B 빡빡해 독립적으로 발화하지 못한다.

대체 지표 셋:

| # | 지표 | 명령 | 현재 |
|---|---|---|---|
| L1 | **압축 첫 로드 바이트, 두 표면 합계 ≤ 62,000 B** | 두 표면을 `gzip -9 -c \| wc -c` | 58,718 B (S0 후) |
| L2 | **첫 로드 요청 수 ≤ 10** | `dashboard_assets` 항목 수 + `index.html` | 7 (S1 후 8) |
| L3 | **단계별 소스 델타 상한** | §6 각 단계 | S0 +100 / S1 +2,400 / S4 +1,500 / S5 순감>0 / S6 +900 |

L3의 합을 천장이라 부르지 않는다. §7-5의 하드코딩 파일 목록은 쓰지 않고 `api/app.py:45-52`의 allowlist에서 파생한다 — 그래야 나중에 추가된 자산이 측정을 빠져나가지 못한다.

**절대 금지(단계 무관):** 번들러·npm·외부 CDN·웹폰트·별도 프론트엔드 런타임.

## 8. 수용 기준

| # | 기준 | 명령 |
|---|---|---|
| 1 | 하네스 무회귀 | `python tools/harness/rosy_harness.py lint` 오류가 착수 시점 대비 증가 0 |
| 2 | docs 계약 시험 | `python -m pytest test/test_network_topology_contracts.py test/test_harness_contracts.py -q` |
| 3 | core 모듈 시험 | `PYTHONPATH=src/rosy_core:src python3 -m pytest src/rosy_core/test -q` |
| 4 | control 모듈 시험 | `PYTHONPATH=src/rosy_control:src python3 -m pytest src/rosy_control/test -q` |
| 5 | L1 압축 첫 로드 | §7 L1 명령 ≤ 62,000 B |
| 6 | L2 요청 수 | §7 L2 ≤ 10 |
| 7 | 잔존 0 (**경로 한정 필수**) | `git grep -n "data-tone\|ambient-grid\|eyebrow" -- src/rosy_core/rosy_core/web` 결과 없음 — 경로를 한정하지 않으면 D-72 본문이 이 단어들을 설명하므로 영구 실패한다 |
| 8 | G4 이행 | 값별 신선도 표시 + `delayed`/`disconnected`에서 위험 명령 비활성화 단언 시험 |
| 9 | ADR 무위반 | D-68·D-71·D-23·D-18·D-32·D-73 (리뷰 항목, 자동 시험 아님) |

## 9. G4 증거 소유권과 작업 트리

G4는 **device-validation 계획이 소유하는 게이트**다. 이 계획은 S3·S4로 G4를 **이행**하되, G4의 상태·증거는 **device-validation 계획에만** 기록한다. 이 계획의 progress/logs에는 모듈 게이트만 쓴다.

작업 트리(branch `chore/public-release-prep`, 170개 dirty) 실측:

| 경로 | 상태 | 영향 |
|---|---|---|
| `src/rosy_core/rosy_core/web/*`, `api/app.py`, `protocol/schemas.py`, `sensing/map_raster.py`, `src/*/test/` | **clean** | **S0~S6 오늘 착수 가능** |
| `docs/reference/ROSY API & Protocol Reference.md` | clean | S3의 D-18 동반 수정 안전 |
| `docs/concept/16_...md` | 미추적(`??`) | S7 충돌 위험 없음 |
| `docs/reference/ROSY ADR Log.md` | ` M` | S7이 기다린다 |
| `docs/plans/2026-09-13-...-device-validation-...md` | ` M` | **S4가 아니라 S7에서 쓴다** |
| `navigation/readiness.py`, `tools/harness/rosy_harness.py`, `docs/progress.md`, `docs/logs.md` | 미추적 | S3의 임계값 출처와 **모든 단계의 게이트 명령이 미커밋 도구에 의존한다** — 착수 전 확인 필요 |

## 10. 알려진 한계 (해소하지 않고 기록)

1. **`tokens.css` ↔ `dashboard.html` 교차 패키지 단언은 D-73상 합법적 거처가 없다.** harness의 어느 모듈도 `src/rosy_core`와 `src/rosy_control`을 함께 갖지 않는다. 색 집합의 단일 출처는 S8까지 시험으로 강제되지 않는다.
2. **증거 4상태와 capability 4상태의 의미가 겹친다**(§5). 개명으로 토큰 충돌만 없앴다.
3. **D-7(React, Accepted)과 D-23(로컬 자산, Accepted)이 서로 모순이고 어느 쪽도 Superseded가 아니다.** 이 계획은 D-23에 베팅한다. 토큰 **값**은 프레임워크 무관하게 살아남지만 **S5의 레이아웃과 S6의 렌더러는 D-7 이행 시 폐기된다.**

   **2026-09-17 해소:** 사용자가 D-23 쪽으로 확정했고 **D-75**가 D-7을 대체했다. D-7은 `Superseded by D-75`이며, 로봇 로컬 화면은 빌드 단계 없는 손으로 쓴 정적 자산으로 고정됐다. **S5·S6은 더 이상 베팅이 아니다.**
4. `dashboard.html`이 토큰 사본을 `:13`, `:17`, JS `:585`에 나눠 갖는다. S8로 이월.

## 11. 리뷰에서 확인된 기존 결함 (이 계획이 만든 것이 아님)

1. **응답 압축이 없다** — `rosy_core/api/`에 미들웨어 0건. 첫 로드에서 93,042 B 낭비. → S0
2. **맵 색이 서버와 클라이언트에서 세 값 모두 불일치** — BGR/RGB 채널 역전. wall은 육안으로 뒤집힌다. → S2
3. **status 색이 categorical 자리에 쓰인다** — `map.js:47` 점유 셀과 `:162` pose 마커가 둘 다 `#c4db76`. → S1
4. **`render_png` docstring이 실제 값과 채널 순서가 반대**(`web_node.py:222`). → S2
5. **`stale_after_s`·`policy_reason`이 직렬화되지 않는다** — 서버가 낡음을 판정하지만 그 판정과 임계값이 API로 나오지 않는다. → S3

## 11-A. 실행 기록 (2026-09-17)

승인 범위: S0~S2 + D-7 정리. **완료.**

| 단계 | 결과 | 증거 |
|---|---|---|
| S0 압축 | 완료 | `rosy_core` 797 passed, 10 skipped. 전송 119,606 B → 30,994 B |
| S1 tokens.css | 완료 | 신규 계약 시험 13건. 원시 색: `styles.css` 62곳·`map.js` 3곳 → 0 |
| S2 래스터 색 계약 | 완료 | `rosy_control` 998 passed, 26 skipped. 신규 계약 시험 3건 |
| D-7 정리 | 완료 | **D-75** 추가, D-7 → `Superseded by D-75` |

경량화 게이트: **L1 60,465 B ≤ 62,000 PASS**, **L2 8 ≤ 10 PASS**.

**L3 미달 1건 — S1 소스 상한을 초과했다.** 예산 ≤ +2,400 B, 실제 **+5,061 B**
(`tokens.css` +3,568, `map.js` 팔레트 해석기 +1,415, `index.html` +62,
`styles.css` +16). 압축 뒤에는 +1,884 B이고 L1이 여유 있게 통과하므로
되돌리지 않았으나, 단계 상한을 빗나갔음을 기록한다. 줄이려면 `tokens.css`의
설명 주석이 후보이며, 그 주석이 닫힌 3집합과 S1/S5 경계를 설명한다.

S1에서 잡은 기존 결함 둘(§11-2, §11-3)은 해소했다. `styles.css`에 섞여 있던
둘째 팔레트(`#fbbf24`·`#f87171`·`#6ee7b7`·`#94a3b8`)와 셋째 앰버
(`rgba(244,186,84,·)`)는 토큰으로 옮겼을 뿐 **의미 재배치는 하지 않았다** —
어느 색이 어느 집합인지 정리하는 것은 S5다.

**S3·S4 실행 (2026-09-17).** 사용자 지시로 이어서 처리. G4 게이트 행은
device-validation 계획이 소유하므로 이 단계에서는 쓰지 않는다(S7).

| 단계 | 결과 | 증거 |
|---|---|---|
| S3 서버 판정 | 완료 | `StateSnapshot.evidence` additive. `rosy_core` 809 passed, 10 skipped. API Ref v1.8. envelope `protocol_version` 1.0 유지 |
| S4 클라이언트 게이트 | 완료 | 텔레메트리 8칸만 `data-evidence`. teleop은 pose+velocity `fresh`일 때만. click-to-goal은 pose `fresh`. 클라이언트에 `stale_after_s` 산술 없음 |

**L3 미달 2건 — S4 소스 상한 초과.** 예산 ≤ +1,500 B, 실제 서빙 자산
**+2,425 B** (`app.js` +1,711, `dom.js` +568, `styles.css` +146).
S1과 같이 압축 뒤 L1 여유가 있고 계약 시험이 우선이라 되돌리지 않으며,
상한을 빗나갔음을 기록한다.

**S5·S6 실행 (2026-09-17).** 사용자 지시로 이어서 처리. concept 16 본문
개명과 G4 행은 S7.

| 단계 | 결과 | 증거 |
|---|---|---|
| S5 장식·절차 | 완료 | `eyebrow`/`ambient-grid`/`data-tone`/`Georgia` 웹 경로 0. host 카드 1열+data-step. 게이지 채움 `--paper`. `rosy_core` 814 passed, 12 skipped |
| S6 capability 4상태 | 완료 | inventory descriptor에 `state`+`reason` additive. `blocked`는 이유 필수. 목록은 inventory, CAP-001은 게이트만. 클라이언트 이유 합성 없음 |

서빙 자산 실측(이번 작업 세 파일): `index.html` −987 B, `styles.css` −414 B, `app.js` +899 B. 합 **−502 B**. S5 순감>0 만족. S6 `app.js` +899 ≤ +900.

**S7·S8 실행 (2026-09-17).**

| 단계 | 결과 | 증거 |
|---|---|---|
| S7 거버넌스 | 완료 | concept 16 §5 G4 어휘, §8 `not_provided`, §6 래스터 파이프라인 경계, §10 D-73 한계, §11 G4. D-72 Validation 시험 경로. device-validation G4 HOST 단락(DEVICE HOLD) |
| S8 콘솔 | 완료(역할 분리, 병합 아님) | **D-77** Accepted. compose에 `web_node` 없음. control 페이지 제목은 diagnostic. (b) 병합은 DEVICE 보류 |

이 계획의 실행 범위 S0–S8은 여기까지다. DEVICE/ARTIFACT GO가 아니다.

## 12. RALPLAN 루프 상태

- Planner v1 → Architect(1) → Critic(1) **ITERATE** → Planner v2 → Architect(2) → **Planner v3(이 문서)**
- Architect 지적 7건 중 v2에서 RESOLVED 4건, PARTIAL 2건, NOT RESOLVED 1건(서버 판정 부재)이었고 v3이 전부 반영했다.
- **v3은 아직 Critic 검토를 받지 않았다.** 승인 전 한 바퀴 더 돌릴지는 승인자 결정이다.
- **범위 결정 2026-09-17: Option A 확정.** S0~S7 전 단계를 실행 범위로 두고 S8(콘솔 통합)만 보류한다. S5·S6은 §10-3의 D-7/D-23 위험을 고지받은 뒤 포함하기로 했다.
- 실행 승인은 범위 결정과 별개다. 이 문서는 실행 승인을 받기 전까지 `pending approval`이며, 그때까지 소스 변경·커밋·실행 스킬 위임을 하지 않는다.
- 리뷰가 제기한 사실 주장은 전부 저장소에서 직접 재확인했다(바이트·gzip·스키마·색 값·직렬화 여부·D-73).
