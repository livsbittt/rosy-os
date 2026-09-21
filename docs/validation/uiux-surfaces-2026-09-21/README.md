# UI/UX 표면 평가 — 회차 1–11 (2026-09-21, HOST 트랙 종결)

D-153 첫 회차와 같은 날 실행된 회차 2–7. 판정 단위는 concept 16 §2의 여섯
표면이고, 평가는 세 계층이다 — G1 기계 게이트(값·문법), G2 상태 매트릭스 캡처,
G3 법 체크리스트(사람 최종).

- 회차 조건: Windows HOST, 작업 트리 uncommitted. G1과 G2 캡처는 현재 트리
  재실행이다(D-79).
- 증거 상한: 이 회차의 증거는 LOCAL(브라우저 경로·PIL 렌더)까지다. 어떤
  DEVICE/FIELD 주장도 승격하지 않는다(D-91, D-152).
- 뷰포트 상한: 콘솔 캡처는 전화형 390×844(LOCAL 브라우저)다. 노트북 레이아웃과
  실물 단말(로봇 AP)은 BENCH 회차에서 연다.

## Result

| 표면 | 질문 (§2) | G1 | G2 | G3 | 판정 |
|---|---|---|---|---|---|
| 운용자 콘솔 `/dashboard` | "지금 이 로봇을 보낼 수 있는가?" | GO — 55+10+브라우저 19 | **10/10** | 위반 0 (기계 6+위임 2) | **GO — LOCAL/HOST 분량** |
| 장비 런타임 `/dashboard` | "이 하드웨어가 제대로 올라오고 있는가?" | GO — 같은 묶음 | **HOST 5셀** (실물 값 BENCH) | 위반 0 (기계 6+위임 2) | **GO — LOCAL 한정** |
| Fleet console | "문제 있는 로봇이 어느 것인가?" | **RED — F-11** (동시 세션 토큰 표류, 2 failed) | **9/9 + 선언 뷰포트 1920×1080** | 위반 0 (기계 6+위임 2) | **HOLD — F-11 해소 후 GO 복원** |
| 로봇 얼굴 LCD | "지금 뭘 하려는가?" | GO — 24 passed | 3/5 (만료 명문화) | #3·#7 BENCH + F-07 | **HOLD — BENCH·F-07** |
| control 레거시 진단 | "흡수된 IO 그래프가 무엇을 보이는가?" | — | — | — | **PARKED** (D-77) |
| 게임 호스트 | "피치·공·로봇·골이 보이는가?" | GO — 9+브라우저 3 | **4/4** | 위반 0 (기계 5+법 1+위임 2) | **GO — LOCAL/HOST 분량** |

**HOST 트랙 종결 — 세 표면 GO, 한 표면 HOLD(F-11), 한 표면 PARKED.** GO는 전부
LOCAL/HOST 분량 한정(D-91) — BENCH 회차(`bench-checklist.md`)에서 실물
뷰포트·실물 값·1.5m 가독으로 재판정한다. 판정 근거와 위임 채택(소유자 회차 11
지시) 내역은 [`g3-checklist.md`](g3-checklist.md) 집계. F-11(회차 12 검증)이
Fleet GO를 일시 철회했다 — 소유 세션의 토큰 표류 해소 후 재실행으로 복원한다.

## 발견 (findings)

### F-01 로봇 얼굴 G1 수집 에러 — 재편 잔류 import 불일치 → **해결 (회차 2)**

- 재편(9b77aa)이 선언만 `emotion.*`로 바꾸고 파일은 `rosy_emotion/`에 둠.
  `emotion/` 평탄화로 닫음(재실행 통과, SOURCE/LOCAL GO 복원).

### F-02 카메라 재인증 시험 비결정적 실패 1회 — **종결** (재현 13회 없음)

### F-03 상태 매트릭스 캡처 훅 — 기존 시험 무변경 (회차 2–5)

- `test_dashboard_browser.py`: 오버라이드 4종(robot_state·vision·runtime·
  host network) + `_launch_page(extra_init=...)` + 스크린샷 env 훅. 상태 8종 +
  불가역 confirm 양방향. 기존 시험 무변경 — 18 passed.
- `test_games_board_browser.py` 3시험, `test_fleet_console_browser.py`
  7시험(`_open_console` 헬퍼).

### F-04 로봇 얼굴 카드 증거 어휘 — **처분 완료 (회차 4)**

- 배터리 결측→0% 위경보는 결함으로 수정(결측 `--` 폴백 + 회귀 시험, crit
  픽셀 0 검증). 만료-복귀 모델은 concept 16 §5에 명문화.

### F-05 초기 HTML pose 폴백 "0.000" → **해결 (회차 6)**

- `index.html` 초기값 5건(pose 3·velocity 2)이 "0.000" 하드코딩이어서 첫 데이터
  도착 전 가짜 측정값이 보였다(Law 0). dom.js `setText` 폴백 규약대로 `—`로
  교체(브라우저 스위트 18 passed 재검증, first-boot 캡처 재생성).

### F-06 숨은 패널의 스크린샷 — DOM 단얜과 화면이 갈라졌다 → **해결 (회차 5)**
- 회차 4의 장비 런타임 상태 캡처(runtime-normal 등)는 operate 뷰에서 찍혀
  카드가 한 장도 안 보였다. `#dds-rmw`·네트워크 카드는 `#view-inspect-panel`
  (기본 `display:none`) 안에 있고, **innerText가 렌더링 안 된 요소에서
  textContent로 폴백**하므로 DOM 단얜은 초록이었다. 픽셀 비교(diff 29px, 문자
  1개)로 적발.
- 수정: 해당 상태에서 `#view-inspect` 클릭 후 캡처 + `is_visible()` 단얜 추가
  (rmw·network·runtime-unavailable·pose-x). 재캡처의 픽셀 diff 79만/1.1만/76만
  — 상태가 실제로 보인다.
- 교훈: **상태 캡처는 가시성 단얜을 동반해야 한다** — 숨은 DOM의 초록은 화면의
  초록이 아니다. 이 교훈은 D-153 회차 절차에 이미 반영했다(아래 워크시트 안내).

### F-07 로봇 얼굴 카드의 어휘·문법 긴장 (회차 7) → **문법 명문화·어휘 잔여 (회차 8)**

- **문법(§7.4) — 해결**: §7.4에 웨이크 카드 문단을 추가했다(PWR-003 상태
  스냅숏·`hold_s` 후 의도 표시 복귀·증거 의미는 §5 얼굴 문단). §5 명문화와
  같은 "기존 동작의 법 문서화" 절차.
- **어휘(Law 4) — 잔여**: 카드 라벨이 영문 약어(MODE·NAV·HEALTH)인데 청중은
  행인. 한글 라벨은 한글 폰트 의존을 만든다(`_FONT_CANDIDATES`, DejaVu에 한글
  글리프 없음). 처분(한글 폰트+라벨 / 아이콘화 / 현상 유지)은 소유자 결정 —
  BENCH 1.5m 가독 실측이 입력.

### F-08 정상 그래프의 토픽 마커가 경보 색을 썼다 → **해결 (회차 8)**

- `styles.css`의 `.graph-topic` 채움이 `--status-warn` — 정상 ROS 그래프에
  항상 따뜻한 점이 그려져 D-82 "따뜻한 것이 보이면 언제나 무언가 잘못된
  것이다"와 concept 16 §6(status=임계 통과 전용)을 위반했다. D-153 회차가
  값을 재지 않으면 이 위반은 계속 "잘 되는 것"으로 보였을 것이다.
- 수정: `--series-primary`(series 대역 — 발행 간선과 같은 집)으로 이동.
  노드·토픽 구분은 형태(사각·원)가 이미 담당(Law "형태가 먼저").
- 행동 게이트: runtime-normal 상태에서 토픽 계산색 ≠ `--status-warn` 계산색
  (캔버스 fillStyle 동일 정규화 — 첫 게이트는 문자열 형식 불일치 동어반복으로
  폐기·재작성). **변이 증명**: warn 되돌림 → 적색, 복원 → 녹색.
- 유지: `.graph-node.foreign`의 crit — 외부 참가자 출현은 경보 의미.

### F-11 동시 세션의 fleet 토큰 표류 — D-129 게이트가 실시간으로 잡음 (회차 12 검증)

- 회차 11 GO 선언 직후 재검증("진짜야?")에서 fleet G1 **2 failed** — 동시
  세션의 미커밋 변경(`console.js`·`index.html`·`styles.css` +69줄)이 단일
  토큰 파일에 없는 `--bg-elevated`·`--bg-surface`·`--text-dim`을 참조.
  D-82 어휘 밖의 범용 콘솔 CSS 이름 — D-130이 경고한 복제 경로의 실례.
- **게이트가 작동했다**: 값 계약이 침입을 몇 시간 안에 적발.
- **본 회차 실수도 기록**: 회차 11에서 Fleet GO 선언 시 G1을 재실행하지
  않았다(D-79 위반) — 판정 직전 재실행이 어째서 규칙인지의 실례.
- 조치: Fleet 판정 GO→**HOLD**(blocker: F-11). 수정은 소유 세션 몫 —
  토큰을 단일 파일 어휘로 바꾸거나 선언을 추가한 뒤 G1 재실행. 본 세션은
  그들의 파일을 건드리지 않는다.

### F-10 점검 순서가 §7.2 기동 순서를 어겼다 → **해결 (회차 10)**

- §7.2 순서표는 "..., DDS domain, ROS graph, **release, commissioning**"인데
  DOM은 릴리즈·커미셔닝 카드를 네트워크 패널 안 **그래프 앞**에 두었다. 순서는
  게이트가 없어 표류했다(기존 게이트는 패널 존재만 단얜).
- 수정: 두 카드를 ROS 그래프 섹션 뒤로 이동(자체 `host-card-grid`). 이동
  안전성 실증 — CSS 클래스 스코핑·JS 컨테이너 의존 0·스텝 번호(1→그래프→2→3)는
  기동 순서와 일치. 의존 논리도 정합(커미셔닝은 그래프 건강 뒤).
- 게이트: `test_the_inspect_order_follows_bringup_order` 신설 — 순서 뒤집기
  변이 → 적색 → 복원 → 녹색(10 passed). 점검 뷰 캡처 4종 재생성.

### F-09 정상 상태의 따뜻한 색 예산 — 페이지 전체 기계 스캔 (회차 9)

- 세 게이트가 색 예산을 기계 판정으로 닫았다:
  1. **콘솔 warm 스캔** — fresh 상태에서 보이는 전요소의 계산색·배경을 토큰
     경보색과 비교(캔버스 동일 정규화·가시 필터). 실측 히트 = **E-Stop 채움
     하나** — Law 3 "위험은 채움이다"가 유일한 crit 면이라는 것이 페이지 전체
     수준에서 실증됐다. 변이 증명: `#robot-id` warm 주입(적용 확인 후) → 적색.
  2. **Fleet 로봇별 색 예산 카운트** — 대형 활성 로스터
     `{rosy_01: 0, rosy_02: 0, rosy_03: 2}` — 색칠은 문제 있는 한 대에만(§7.3
     "one coloured row"). 첫 단얜(warn 0)은 대기 태그로 적색 — 단얜이 물린다는
     증거이자, 대기 warn이 합법 예외임을 배우는 계기가 됐다.
  3. **Cyclone 적용 confirm 양방향** — 불가역 기계 증명 3경로(모드·Cyclone
     저장+재부팅 D-123·Fleet 전체 정지)로 확장.
- 결과: 콘솔 #3·#5, Fleet #3, 장비 #5가 기계 확정으로 승격.

## 표면 카드

### 1. 운용자 콘솔 — CORE `/dashboard` operate 뷰 (현장 운용자)

- **G1:** core 묶음 **55 passed** + `test_console_layout.py` **9 passed**(공간
  문법 게이트) + 옵트인 브라우저 **19 passed**(F-09 warm 스캔·Cyclone confirm
  포함).
- **G2 — 상태 10/10 완결(전화 390×844):** fresh(전체 operate 뷰 + 요소 2) /
  delayed / disconnected(값별 `data-evidence`, 가시성 단얜) / unavailable
  (vision "수신 대기") / 빈 목록(설정 패널 waypoint "없습니다" + dock HOLD) /
  최초 기동(fetch 미해결) / 오류·거부(401·429) / SAFE_STOP / 불가역 확인
  (confirm 양방향, `app.js:986`).
- **G3:** 미실행 — 워크시트 8항 근거 채움 완료.
- **판정:** HOLD — blocker: G3 사람 판정, 노트북 뷰포트(BENCH).

### 2. 장비 런타임 — CORE `/dashboard` inspect 뷰 (설치자·정비자)

- **G1:** 같은 core 묶음 55 passed.
- **G2 — HOST 분량 완결, 5셀(전화 390×844, inspect 뷰):**
  - unavailable — `console_runtime-unavailable_…png`("그래프 수집 불가"
    risk 항목, 가시성 단얜)
  - runtime-normal — 그래프 OK·`rmw_cyclonedds_cpp`·LOOPBACK ONLY·SITE_STA·
    네트워크 속도(단얜 4종+가시성)
  - rmw-mismatch — `rmw_fastrtps_cpp` + `RMW_MISMATCH` risk 항목(D-121 웹은
    보고만)
  - 네트워크 모드 3값 — SITE_STA(runtime-normal)·RELAY_AP_STA·
    PROVISIONING_AP(칩 가시성 단얜)
  - 잔여는 전부 실물 의존: 실제 Pi `/proc`·thermal 값, 실 RMW 정정 장면(BENCH)
- **G3:** 미실행 — 워크시트 근거 채움 완료.
- **판정:** HOLD — blocker: G3 사람 판정, 실물 host 값(BENCH).

### 3. Fleet console (관제자)

- **G1:** 12 passed + 옵트인 브라우저 **7 passed**(회차 5 재실행).
- **G2 — 9/9 완결(1280×720 HOST):** fresh(대형 활성) / delayed(팔로워 1.2 Hz
  "지연" warn) / disconnected(팔로워 "끊김" crit) / 연락 두절(오프라인 로봇
  "닿지 않음: CONNECT_ERROR" + OFFLINE — §5 두절은 자기 상태) / 빈 플릿
  (0/0, 오버레이 0) / gather 오류("Fleet 서버 없음") / HOLDING 이유(warn 태그 +
  재개 버튼 활성 + 맵 칩 "HOLD · STREAM_LOST") / 중재 대기(blocked_by 점선) /
  불가역 확인(전체 정지 confirm 양방향, `console.js:529`).
- **G3:** 미실행 — 워크시트 근거 채움 완료.
- **판정:** HOLD — blocker: G3 사람 판정. 사이트 PC 실물 뷰포트는 BENCH.

### 4. 로봇 얼굴 — `emotion` LCD (행인)

- **G1:** **24 passed**(F-01 해결 + F-04 회귀 + 회차 6 캡처 재현 시험).
- **G2 — 3/5:** fresh(정상·배터리 임계색·E-STOP)·최초 기동(`--` 폴백, crit
  픽셀 0). delayed/disconnected는 만료-복귀 모델로 명문화(concept 16 §5).
  **캡처는 저장소에서 재현 가능** — `test_info_screen_capture.py`(옵트인,
  `ROSY_FACE_CAPTURE_DIR`). LCD 실물 사진은 BENCH.
- **G3:** 미실행.
- **판정:** HOLD — blocker: G3, LCD 실물(BENCH).

### 5. control 레거시 진단 — PARKED (D-77)

### 6. 게임 호스트 — `games` match board (노트북 경기 운용자)

- **G1:** 9 passed + 옵트인 브라우저 **3 passed**.
- **G2 — 4/4 HOST 분량:** 정상 play·유실 HOLD·최초 기동·무장 확인(`--drive`
  플래그 게이트, D-108 코드 증거).
- **G3:** 미실행 — 워크시트 근거 채움 완료.
- **판정:** HOLD — blocker: G3 사람 판정.

## G3 체크리스트 — [`g3-checklist.md`](g3-checklist.md)

사람 판정 워크시트(8항 × 표면, 근거 미리 연결). **회차 8까지 기계 판정 완료:**

| 표면 | 기계 확정 | 부분(기계) | 순수 사람 |
|---|---|---|---|
| 운용자 콘솔 | 6 | 1 | 1 |
| 게임 호스트 | 5 | 0 | 3 |
| Fleet | 6 | 0 | 2 |
| 장비 런타임 | 5 | 1 | 2 |
| 로봇 얼굴 | 5 (+N/A 1) | 1 | 1 (F-07 어휘) |

회차 9에서 색 예산 2건(F-09 스캔·Fleet 카운트)과 Cyclone confirm을 기계
확정으로 닫았다 — 기계 확정 **27슬롯**. 남은 사람 몫: 표면 질문 5(종합)·
위계 체감 2·게임 공 색 1·부분 3건 확인·F-07 어휘(소유자)·서명.

## BENCH 회차 — [`bench-checklist.md`](bench-checklist.md)

실물 분량의 실행 프로토콜(회차 8 예정): 실물 단말 캡처, 실물 Pi host 값, 실
RMW 정정 장면 전후, LCD 1.5m 사진, 만료-복귀 실측, 종결 절차.

## 공통화 평가 (회차 6 — "더 공통 컴포넌트화")

- **제품 표면: 추가 공유 없음이 정답.** D-92/D-129가 시각 컴포넌트 공유를
  명시적으로 기각했고(Fleet이 콘솔처럼 보이는 것이 결함 — concept 16 §4),
  D-130의 headless 로직 추출 자격("로직이 있고 둘 이상의 표면이 필요")에
  맞는 후보가 현재 0개다. 증거 어휘는 표면마다 다른 도메인(릴레이 스트림·
  로봇 값·경기 관측)의 *번역*이지 중복 로직이 아니다. 공유되어야 할 것 —
  법(L1)·토큰(`tokens.css`)·어휘표 — 은 이미 공유돼 있다.
- **시험 도구: 공유화 완료.** `test/browser_harness.py` 신설 — 실행 옵션·
  오류 수집·confirm 스텁(거부/수락, `; null` 교훈 내장)·TEMP 스크린샷 배관을
  세 브라우저 시험이 함께 쓴다(`robot_contracts.py` 관례). 제품 표면이 아니므로
  D-92와 충돌하지 않는다.
- **캡처 재현 가능화:** 로봇 얼굴 4종 카드가 저장소 시험(`test_info_screen_
  capture.py`, 옵트인)에서 재생성된다 — 이제 전 표면 G2 캡처가 저장소에서
  재현 가능하다.

## 증거 파일 (28)

| 파일 | 표면 | 셀 | 검증 |
|---|---|---|---|
| `console_full_390x844_manual-host-unavailable-local.png` | 운용자 콘솔 | MANUAL fresh(operate 뷰 전체) | 기계 단얜 + PIL |
| `console_traffic-policy_host-sim.png` | 운용자 콘솔 | 관제 정책 `ENFORCED` | 기계 단얜 + PIL |
| `console_camera-region_host-sim.png` | 운용자 콘솔 | 카메라 영역(fresh) | 기계 단얜 + PIL |
| `console_delayed_390x844_local.png` | 운용자 콘솔 | `delayed` | `data-evidence`+가시성+PIL |
| `console_disconnected_390x844_local.png` | 운용자 콘솔 | `disconnected` | `data-evidence`+가시성+PIL |
| `console_unauthorized_390x844_local.png` | 운용자 콘솔 | 401 권한 거부 | drawer 단얜 + PIL |
| `console_safe-stop_390x844_local.png` | 운용자 콘솔 | `SAFE_STOP` + estop | 모드 단얜 + PIL |
| `console_vision-unavailable_390x844_local.png` | 운용자 콘솔 | vision unavailable | "수신 대기" 단얜 + PIL |
| `console_first-boot_390x844_local.png` | 운용자 콘솔 | 최초 기동 | API 0건 단얜 + PIL |
| `console_field-settings_empty-waypoints-dock-hold_local.png` | 운용자 콘솔 | 빈 waypoint + dock HOLD | 단얜 2종 + PIL |
| `console_runtime-unavailable_390x844_local.png` | 장비 런타임 | unavailable(inspect) | risk 가시성 단얜 + PIL + diff 76만px |
| `console_runtime-normal_390x844_local.png` | 장비 런타임 | 그래프·RMW·SITE_STA·속도 | 단얜 4종+가시성 + PIL |
| `console_rmw-mismatch_390x844_local.png` | 장비 런타임 | RMW 정정 대기 + risk | 단얜 2종+가시성 + diff 79만px |
| `console_network-relay_390x844_local.png` | 장비 런타임 | RELAY_AP_STA | 칩 가시성 단얜 + diff 1.0만px |
| `console_network-provisioning_390x844_local.png` | 장비 런타임 | PROVISIONING_AP | 칩 가시성 단얜 + diff 1.1만px |
| `fleet-console_1920x1080_formation-active.png` | Fleet | 대형 활성(상태 인스턴스 4) | 기계 단얜 + PIL |
| `fleet-console_1920x1080_empty-local.png` | Fleet | 빈 플릿(0/0) | 오버레이 0 단얜 + PIL |
| `fleet-console_1920x1080_gather-error-local.png` | Fleet | gather 오류 | "Fleet 서버 없음" 단얜 + PIL |
| `fleet-console_1920x1080_delayed-local.png` | Fleet | 팔로워 지연(1.2 Hz) | "지연"·"끊김" 단얜 + PIL |
| `fleet-console_1920x1080_unreachable-local.png` | Fleet | 연락 두절 로봇 | "닿지 않음"+OFFLINE 단얜 + PIL |
| `fleet-console_1920x1080_holding-local.png` | Fleet | HOLDING 이유 | warn 태그·재개 버튼 단얜 + PIL |
| `robot-face_info-card_320x240_fresh-nominal-local.png` | 로봇 얼굴 | fresh(정상) | render() + PIL |
| `robot-face_info-card_320x240_fresh-battery-crit-local.png` | 로봇 얼굴 | fresh(임계색) | render() + PIL |
| `robot-face_info-card_320x240_fresh-estop-local.png` | 로봇 얼굴 | fresh(E-STOP) | render() + PIL |
| `robot-face_info-card_320x240_first-boot-empty-local.png` | 로봇 얼굴 | 최초 기동(`--`) | **crit 픽셀 0** + PIL |
| `game-host_board_1280x800_play-noframe-local.png` | 게임 호스트 | 정상 play | DOM 단얜 + PIL |
| `game-host_board_1280x800_lost-hold-local.png` | 게임 호스트 | 유실 HOLD | `#lost` 단얜 + PIL |
| `game-host_board_1280x800_initial-local.png` | 게임 호스트 | 최초 기동 | "대기" 단얜 + PIL |

PIL 비공백 전 파일 통과. inspect 뷰 4종은 상호 픽셀 diff로 상태 렌더를 교차
검증했다(F-06 수정 증거).

## Reproduce

```powershell
# G1 — 현재 트리 재실행 (Windows HOST)
python -m pytest src/core/core/test/test_palette_gates.py src/core/core/test/test_ui_token_contracts.py src/core/core/test/test_evidence.py src/core/core/test/test_evidence_margin.py src/core/core_api_web/test -q   # 55 passed
python -m pytest src/site/fleet/test/test_grammar_separation.py src/site/fleet/test/test_console_palette.py -q   # 12 passed
python -m pytest src/apps/games/test/test_preview.py src/apps/games/test/test_visibility.py -q                    # 9 passed
$env:PYTHONPATH="src/apps/emotion"; python -m pytest src/apps/emotion/test/test_info_screen.py src/apps/emotion/test/test_info_screen_palette.py -q   # 23 passed

# G2 캡처 (옵트인 Chromium)
$env:ROSY_RUN_BROWSER_TESTS="1"
$env:ROSY_DASHBOARD_STATE_SHOT_DIR="<이 폴더>"                     # console_{…}_*.png 8종
$env:ROSY_DASHBOARD_SCREENSHOT="<이 폴더>\console_traffic-policy_host-sim.png"
$env:ROSY_CAMERA_DASHBOARD_SCREENSHOT="<이 폴더>\console_camera-region_host-sim.png"
$env:ROSY_DASHBOARD_FULL_SCREENSHOT="<이 폴더>\console_full_390x844_manual-host-unavailable-local.png"
$env:ROSY_FIELD_SETTINGS_SCREENSHOT="<이 폴더>\console_field-settings_empty-waypoints-dock-hold_local.png"
python -m pytest test/test_dashboard_browser.py -q                 # 18 passed
python -m pytest test/test_games_board_browser.py -q               # %TEMP%\games_board_*.png 3종 → 복사
python -m pytest test/test_fleet_console_browser.py -q             # %TEMP%\fleet_console_*.png 6종 → 복사

# 로봇 얼굴 G2 (render PIL — 저장소에서 재현)
# $env:PYTHONPATH="src/apps/emotion"; $env:ROSY_FACE_CAPTURE_DIR="<이 폴더>"; python -m pytest src/apps/emotion/test/test_info_screen_capture.py -q
```

## 다음 회차 과제 (회차 8 — BENCH)

1. [`bench-checklist.md`](bench-checklist.md) 실행 — 실물 뷰포트·LCD 사진·실물
   Pi 값·실 RMW 정정. BENCH 판정 입력이 F-07을 닫는다.
2. G3 사람 최종 판정·서명 — 위반 0 표면부터 GO(BENCH 분량 한정 표기).
