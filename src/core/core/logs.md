# core logs

추가만 한다. 형식: [module harness 설계](../../docs/plans/2026-09-15-module-harness-design.md) §4.2.
2026-09-15 이전 이력은 [흡수 결과](../../docs/plans/2026-09-12-control-absorption-results.md)와 `git log -- src/core`를 본다.

## 2026-09-15 · uncommitted · docs(harness): start the core harness pilot
- 변경: `progress.md`, `logs.md`, 생성 `index.md` 추가. `AGENTS.md`에 기록 위치와 작업 순서 연결
- 증거: `PYTHONPATH=src/core;src/control;src python -m pytest src/core/test -q` 759 passed, 10 skipped (Windows, 미커밋 WIP 포함 작업 트리)
- gate 변화: 없음. 기존 SOURCE/LOCAL/ROS-SIM GO, ARTIFACT/DEVICE HOLD, FIELD PARKED를 스냅샷으로 옮김
- 결정: D-61 Proposed
- 교훈: 없음

## 2026-09-15 · uncommitted · docs(harness): stop carrying over unrerun ROS-SIM evidence
- 변경: 리뷰 반영. `last_verified.commit`을 `uncommitted`로, SOURCE에 재실행 명령 추가
- 증거: `python -m pytest test/test_harness_contracts.py test/test_network_topology_contracts.py -q` 62 passed; `python tools/harness/rosy_harness.py lint` 0 errors, 2 warnings(uncommitted). ROS 시험 자체는 미실행
- gate 변화: ROS-SIM GO→HOLD (2026-09-13 증거를 재실행 없이 GO로 옮겼던 것을 정정)
- 결정: 없음
- 교훈: 없음

## 2026-09-17 · uncommitted · feat(web): compress dashboard assets and make tokens.css the single source of colour
- 변경: S0 — `api/app.py`에 `GZipMiddleware(minimum_size=1024)` 추가. S1 — `web/tokens.css` 신규(닫힌 3집합 + 래스터 토큰), `styles.css`의 원시 색 62곳을 토큰 참조로 치환(값 보존), `map.js`가 캔버스 색을 tokens.css에서 읽도록 변경, `index.html`이 tokens.css를 styles.css보다 먼저 링크, allowlist에 `tokens.css` 한 줄 추가. 신규 `test/test_ui_token_contracts.py` 13건과 `test_dashboard.py` 압축 시험 2건
- 증거: `PYTHONPATH=src/core;src python -m pytest src/core/test -q` 797 passed, 10 skipped (2026-09-17 Windows, 미커밋 WIP 포함 작업 트리; 이 호스트 python3에 PyYAML이 없어 `python` 3.14.5 사용). 전송량(LF 정규화): 원본 119,606 B → gzip 30,994 B. L1 압축 첫 로드 두 표면 합계 60,465 B ≤ 62,000 PASS, L2 요청 8 ≤ 10 PASS
- gate 변화: 없음. SOURCE/LOCAL GO 유지하되 LOCAL 증거를 759→797로 갱신
- 결정: D-72 (Proposed) 이행 S0·S1. 계획은 `docs/plans/2026-09-17-interface-design-implementation-design.md`
- 교훈: 계획의 S1 소스 상한(+2,400 B)을 초과했다 — 실제 +5,061 B(tokens.css 3,568 + map.js 팔레트 해석기 1,415). 압축 뒤에는 +1,884 B이고 L1 게이트는 통과하므로 되돌리지 않았으나, 단계 상한은 빗나갔음을 기록한다. 원시 색 계약 시험이 기존 결함 둘을 잡았다: `map.js`가 점유 셀과 pose 마커에 status 색 `#c4db76`을 쓰고 있었고, `styles.css`에 선언된 팔레트 밖의 둘째 팔레트(#fbbf24·#f87171·#6ee7b7·#94a3b8)와 셋째 앰버(rgba(244,186,84,·))가 섞여 있었다

## 2026-09-17 · 8fdd8d2 · feat(core): D-72 S3–S6 evidence, gauges, inventory states
- 변경: StateSnapshot.evidence, dashboard data-evidence와 teleop 게이트, 장식 제거, inventory state+reason
- 증거: `PYTHONPATH=src/core;src python -m pytest src/core/test -q` 814 passed, 12 skipped (2026-09-17 Windows)
- gate 변화: 없음. LOCAL GO 유지. ARTIFACT/DEVICE HOLD
- 결정: D-72 S3–S6. G4 HOST 조각이며 DEVICE GO가 아니다
- 교훈: 없음

## 2026-09-17 · uncommitted · feat(web): regenerate the palette from OKLCH and gate its values
- 변경: `web/tokens.css`를 OKLCH에서 생성한 값으로 교체(바탕 중립화, 경보 2색, 계열은 차가운 띠, 래스터 무채색, `--route-dim`·`--series-goal` 추가, 중복 팔레트 병합). 신규 `test/test_palette_gates.py` 10건 — 표준 라이브러리만으로 OKLCH·WCAG·적록 색약을 계산해 값 자체를 단언한다
- 증거: `PYTHONPATH=src/core;src python -m pytest src/core/test -q` 826 passed, 10 skipped (2026-09-17 Windows, 미커밋 WIP 포함 작업 트리). 팔레트 게이트 실측: 신호 색 채도 전부 >= 0.133, 주의·위험 지각 밝기 차 0.30, 색약 대비 2.05:1, 위험 면 위 잉크 5.3:1, 실선 대 파선 색약 2.06:1, 래스터 채도 <= 0.01 단조, 본문 대비 >= 4.5:1
- gate 변화: 없음. SOURCE/LOCAL GO 유지하되 LOCAL 증거를 814→826으로 갱신
- 결정: D-82 Proposed. `control`은 건드리지 않는다(D-77로 레거시 진단, concept 16 §6이 별개 파이프라인)
- 교훈: 이전 팔레트는 적록 색약 시야에서 위험 대 주의 대비가 1.07:1이었다 — 로봇 콘솔에서 주의와 위험이 구분되지 않았고, 위험이 셋 중 가장 밝았다. HSL로 보면 밝기 3pt 차이라 멀쩡해 보였고, 지각 밝기 차는 0.009였다. 색을 눈으로 고르면 이 결함은 보이지 않는다. 그리고 현대 팔레트를 그대로 베끼면 같은 함정에 빠진다 — Radix 9나 Tailwind 500이 예뻐 보이는 이유가 모든 색상을 같은 밝기에 두기 때문이고, 그 균일 밝기가 정확히 색약 분리를 파괴한다(측정치 1.22:1). 브랜드 액센트와 의미 인코딩은 다른 작업이다

## 2026-09-17 · uncommitted · feat(web): finish the D-82 pass — component tokens, typography, touch targets
- 변경: `web/tokens.css`에 컴포넌트·치수 토큰 층 추가(space 6 · radius 4 · target 3 · surface 3 · nominal 2 · button/field/flag/gauge · `--focus-ring` · `--series-secondary`)과 타이포그래피 토큰을 `styles.css`에서 이관. `styles.css` 의미 재배치 22곳(초록 참조 0), 장식 3개 제거(body gradient wash · 패널 wash · 드롭섀도), 44px 미만 터치 타겟 5곳을 `--target-secondary`로. `test_ui_token_contracts.py`에 게이트 8건 추가
- 증거: `python -m pytest src/core/test/test_ui_token_contracts.py src/core/test/test_palette_gates.py -q` 31 passed; `python -m pytest src/core/test -q` 836 passed, 1 failed, 10 skipped (2026-09-17 Windows). 실패 1건은 `test_module_criteria.py::test_c6_seam_reaches_match_the_published_triage`이며 피어 커밋 `7f674f9`의 `safety/manager.py` getattr 도달이 C6 문서 분류에 없어서다 — 이 변경과 무관하고 웹 파일을 건드리지 않는다
- gate 변화: 없음
- 결정: D-82 적용 범위를 색에서 컴포넌트·치수·글자까지 넓혔다. 전면 간격 정규화(px 243 · rem 101, 344곳)는 브라우저 회귀 시험이 CI에 없어 하지 않았다 — 남은 일로 기록한다
- 교훈: 토큰을 선언만 하고 쓰지 않으면 결함이 숨는다. 치수 토큰 13개가 사용처 0이었고, 채택하자마자 44px 미만 터치 타겟 5곳이 드러났다(설정·호스트 입력 42px, 지도 툴바 34px, 웨이포인트 32px). 폰트도 같은 종류였다 — `Aptos`는 MS Office 전용이라 Linux·macOS에서 라틴이 한글 서체로 떨어지고, `Malgun Gothic`이 없어 Windows에서는 한글이 스택 전체를 빠져나가며, 등폭에 macOS 항목이 없어 계기 숫자가 Courier로 떨어지고 있었다

## 2026-09-18 · uncommitted · feat(web): triage the console, age stale values, stop shipping em dashes
- 변경: `web/triage.js` 신규 — 서버가 이미 보내는 것(estop · battery_status · 채널별 evidence · navigation · inventory blocked)만 읽어 고장을 파생하고, `CATEGORY_ORDER` 선언 표로 정렬한다. `index.html`에 머리 자리 추가(고장이 없으면 렌더하지 않는다), `app.js`가 상태·inventory 양쪽에서 다시 분류. `dom.js`가 delayed/disconnected에 나이를 노출하고 CSS가 그린다. 배송 마크업의 em dash 45곳 제거 + `requested` 플래그로 첫 fetch 전에는 빈칸. `api/app.py` allowlist에 triage.js
- 증거: `python -m pytest src/core/test -q` 856 passed, 1 failed, 10 skipped (2026-09-18 Windows, 피어 미커밋 포함 트리). 신규 계약 시험 16건(triage 7 · margin 4 · first-paint 5). 실패 1건은 `test_c6_seam_reaches_match_the_published_triage`이며 피어 커밋 `7f674f9`의 `safety/manager.py` getattr 도달이 C6 문서 분류에 없어서다 — 이 변경은 `web/`·`api/app.py`·`test/`만 건드린다. 루트 계약 73 passed, lint 0 errors
- gate 변화: 없음
- 결정: 서버 계약을 바꾸지 않는다. 셋 다 S3·S4가 이미 배송한 데이터만 소비한다. 임계값(`stale_after_s`)은 읽지 않는다 — 피어가 커밋한 게이트(`test_dashboard.py:427-429`)가 클라이언트 접근을 금지하며, 표시와 재계산은 다르지만 그 경계를 이 세션이 일방적으로 옮기지 않았다
- 교훈: 고침과 그 고침을 지키는 시험이 같은 좁은 패턴을 인코딩하면 둘 다 같은 구멍을 갖는다. em dash를 `>—<` 모양으로만 찾아 지웠고 시험도 같은 정규식을 썼더니 `SEQ —`·`voltage —`처럼 라벨이 앞에 붙은 4곳이 고침과 시험 양쪽을 빠져나갔다 — 리뷰어가 잡았다. 시험을 "텍스트가 대시로 끝나는 id 자리"로 넓히고 수정 전 마크업에 걸어 45곳을 잡는지 확인했다. 그리고 `표본 수집 대기` 같은 문구를 처음에 같은 결함으로 봤으나, 그건 "아직 안 물어서 기다린다"를 산문으로 말한 것이라 결함이 아니다 — `상태 없음` 하나만 "물었는데 없다"로 읽혀 기존 관용구 `확인 전`에 맞췄다


## 2026-09-18 · uncommitted · fix(core): 보고 pose 의 임자를 map 프레임으로 못박는다
- 변경: `bridge/odometry.py` 에 `odom_owns_pose()`, `ros_bridge` 가 map→base TF 를 읽은 시각을 기억하고 그것이 신선하면 odom 콜백은 pose 를 건드리지 않는다. 시험 2건(`test_bridge_odometry.py`)
- 증거: 미로 주행 뒤 실측 — Gazebo 정답 (2.005, 2.181), TF `map→base` (1.969, 2.228) 로 AMCL 은 6 cm 안에 있었는데 `/api/v1/robot/pose` 는 (4.219, 4.590) 을 돌려줬다. 그 값은 `/rosy_01/odom` 과 정확히 같다. 수정 뒤 같은 시나리오에서 측위 오차 3.27 m → 0.03 m
- gate 변화: 없음
- 결정: 없음
- 교훈: pose 를 쓰는 곳이 둘이었고(odom 콜백 약 30 Hz, state 틱 10 Hz) 주기가 높은 쪽이 조용히 이겼다. 좌표를 읽는 쪽(관제 화면, 미션 판정, 대시보드)은 전부 map 프레임을 뜻하므로 그쪽이 임자다. odom 은 지역화가 없는 구성의 폴백으로만 남긴다

## 2026-09-18 · uncommitted · refactor(web): give the dashboard the spatial grammar it was designed for
- 변경: `/dashboard`를 한 문서 안의 두 뷰로 나눴다. **운용**(`.console`)은 고정 3분할(감지 264 / 관측 1fr / 조작 340)이고 페이지가 스크롤하지 않는다. **점검**(`.inspect`)은 기동 순서 수직이며 여기서만 스크롤한다. 섹션 11개를 이름·id·aria-label 하나 안 바꾸고 각 영역으로 옮겼다. 상단에 뷰 전환, 비상정지를 조작 영역 맨 위로(DOM 순서), 좁은 칸용 타이포 한 벌, `--topbar-height` 토큰 신설. `map.js`는 크기를 모르면 `undefined×undefined` 대신 "크기 미상"을 쓴다
- 증거: `python -m pytest src/core/test -q` 866 passed, 10 skipped (2026-09-18 Windows). 신규 `test_console_layout.py` 8건, `test_ui_token_contracts.py`에 위험 면 잉크 짝 게이트 1건. Playwright 1280×720 실측: pageScroll 3582→**0**, 상태줄 158→**65**, 관측 영역 363→**455**, 지도 24→**191**, 비상정지 y=832(화면 밖)→**331**
- gate 변화: 없음
- 결정: 두 문법을 한 화면에 섞지 않는다(concept 16 §4 L2). 점검 뷰의 패널은 지우지 않고 옮겼다 — 설치·정비가 쓰는 화면이고 절차 문법이 맞는 자리다
- 교훈: 시험이 전부 통과해도 화면은 안 뜰 수 있다. 기존 브라우저 시험이 **CSS를 빈 문자열로 서빙**해서 배치는 한 번도 검증된 적이 없었고, 실제로 렌더해 재 보니 네 개의 결함이 한 번에 나왔다 — `[hidden]`이 `display:flex`에 져서 숨긴 뷰가 레이아웃을 먹고 있었고(3582px 스크롤), `aspect-ratio: 5/3`이 `flex:1`과 싸워 지도를 54px로 눌렀고, `hero-copy`의 `padding: 50px`이 상태줄을 141px로 만들었고, 존재를 잊고 있던 `.page-footer`가 64px를 더하고 있었다. 그리고 내가 `#page-footer`로 셀렉터를 썼는데 그건 클래스였다 — 재보지 않았으면 못 찾았다. 마지막으로 D-82가 위험을 어두운 빨강으로 바꾼 뒤 옛 옅은 빨강에 맞춰진 어두운 잉크가 대비 2.86:1로 남아 있었다. 값만 보는 게이트는 CSS 안의 **짝**을 못 본다 — 짝을 보는 게이트를 새로 넣었다


## 2026-09-18 · uncommitted · refactor(web): float the map controls so the map gets the observe region back
- 변경: `.field-map-panel` 흐름에 있던 지도 툴바 두 줄(레이어·클릭 동작)을 `.map-stage` 안으로 옮기고 `.map-controls`로 묶어 지도 위 좌상단에 겹쳤다. 겹친 칩은 `--scrim` 바탕과 `--surface-line` 테두리로 점유 격자와 갈린다. `test_console_layout.py`에 게이트 1건
- 증거: `python -m pytest src/core/test -q` 867 passed, 10 skipped (2026-09-18 Windows). 루트 계약 921 passed, lint 0 errors. Playwright 1280×720 실측: 지도 191→**307px**(관측 영역 467 중), pageScroll 0 유지, 페이지 오류 없음
- gate 변화: 없음
- 결정: 범례와 안내 문구는 지우지 않고 흐름에 남겼다 — 읽는 것이지 조작하는 것이 아니라 겹치면 지도를 가린다. 툴바만 겹친다
- 교훈: 고정 높이 영역에서는 보조 요소가 전부 주 요소의 예산에서 나온다. 관측 영역 455px 중 지도가 191px이었던 것은 지도가 작아서가 아니라 툴바 두 줄·범례·안내가 264px을 먼저 가져갔기 때문이다. `layerRoot`가 `#field-map-panel`이라 DOM 이동 뒤에도 `[data-map-layer]`·`[data-map-click]` 질의가 그대로 걸린다는 것을 먼저 확인하고 옮겼다

## 2026-09-18 · uncommitted · refactor(web): rewrite the surface rules as one design system
- 변경: `web/styles.css`를 처음부터 다시 썼다(856→약 700줄). 카드 기반 원본 위에 콘솔 패치를 15겹 얹은 구조를 버리고, 콘솔 규칙을 `.console .x` 덮어쓰기가 아니라 제자리에서 정의한다 — 콘솔이 기본형이고 카드 대접은 `.inspect .panel`에만 준다. 별칭 층(`--ink`·`--line`·`--signal-*` 8개) 삭제, `.panel::before` 색 띠 5종과 등장 애니메이션 삭제, 상태 어휘를 하나로 통합(뱃지·기계 태그·모드 칩·`[data-status]`·이벤트 심각도가 같은 셋을 쓴다). `tokens.css`에 글자 계단 `--text-micro|label|body|value|title`과 `--track-label` 신설. 마크업: 비상정지가 제목 `<div>` 안에 중첩돼 있던 것을 꺼내고, 범례·안내를 `.map-stage` 위 오버레이로 이동. 게이트 3건 추가
- 증거: `python -m pytest src/core/test -q` 870 passed, 10 skipped. 루트 계약 923 passed, lint 0 errors. Playwright 실측 — 1280×720: 지도 307→**469px**, 상태줄 44px, pageScroll 0. 900×700: 지도 388×457, 가로 넘침 0. 390×844: 세로로 쌓고 스크롤, 오류 없음. 새 게이트를 이전 stylesheet에 걸면 별칭 8개·계단 밖 간격 118곳(값 53가지)·계단 밖 글자 95곳(68가지)이 잡힌다
- gate 변화: 없음
- 결정: 좁은 화면(≤1080px)에서도 영역 셋의 **자리는 바꾸지 않는다**. 조작을 아래 줄로 돌려 봤더니 그 칸이 제 내용만큼(412px) 가져가 지도가 37px로 눌렸다 — 공간 문법을 버리고 얻는 것이 없었다. 레일 폭만 좁힌다. 휴대폰(≤720px)은 고정 프레임이라는 전제 자체가 없으므로 세로로 쌓고 스크롤을 허용한다
- 교훈: "카드처럼 보인다"는 취향 문제가 아니라 구조가 그렇게 시켜서였다. 제목이 세 층(영역 머리·패널 제목·소제목)이고 층마다 상자를 만들면 화면이 목차로 읽힌다. 제목을 **줄**로 바꾸고(작은 대문자 라벨 + 이어지는 실선 + 오른쪽 기계 값) 값 격자를 1px 간격의 실선 격자로 짜자 같은 데이터가 계기판으로 읽혔다. 그리고 덮어쓰기로 쌓은 규칙은 언제나 원본을 이긴 척만 한다 — `.region .panel { border: 0 }`으로 카드를 지워도 원본의 카드 여백·카드 리듬·카드 타이포가 계속 밀고 올라와 패치가 한 겹씩 늘었다. 원본을 고치는 것이 패치를 얹는 것보다 짧았다

## 2026-09-18 · uncommitted · feat(core): scan/imu/range use sensor-data QoS (D-119)

- 변경: ros_bridge LaserScan/Imu/Range 구독이 qos_profile_sensor_data. RELIABLE depth 10 과 센서 BEST_EFFORT 가 어긋나지 않게.
- 증거: `python -m pytest src/core/test/test_bridge_timers.py test/test_dds_rmw_contracts.py -q`
- gate 변화: 없음. DEVICE PARKED

## 2026-09-18 · uncommitted · feat(core): apply Cyclone before rclpy.init (D-121)

- 변경: `apply_cyclone_rmw` 를 `rclpy.init` 앞에. 스냅샷 `rmw` 필드와 대시보드 표시. FastDDS 기동 거절.
- 증거: `python -m pytest src/core/test/test_rmw.py src/core/test/test_ros_graph_monitor.py src/core/test/test_dashboard.py -q`
- gate 변화: 없음. DEVICE PARKED

## 2026-09-18 · uncommitted · feat(core): correct foreign RMW on next CORE start (D-122)

- 변경: FastDDS/기타 RMW 는 거절하지 않고 Cyclone으로 고친 뒤 init. 커널 reboot 없음.
- 증거: `python -m pytest src/core/test/test_rmw.py -q`
- gate 변화: 없음. DEVICE PARKED

## 2026-09-18 · uncommitted · feat(core): persist Cyclone then Host Agent reboot (D-123)

- 변경: POST /api/v1/system/dds/cyclone. 오버레이 dds.rmw 저장 후 Host Agent system.reboot. 대시보드 확인 버튼.
- 증거: `python -m pytest src/core/test/test_rmw.py src/core/test/test_dashboard.py src/core/test/test_host_cards.py -q`
- gate 변화: 없음. DEVICE PARKED

## 2026-09-18 · uncommitted · feat(core): dashboard AP toggle and Wi-Fi connect (D-124)

- 변경: 네트워크 카드에 AP 켜기/끄기와 SSID·암호 연결. POST /host/network/mode, /connect. PSK는 GET/응답에 안 채움
- 증거: `python -m pytest src/core/test/test_host_cards.py src/core/test/test_dashboard.py -q`
- gate 변화: 없음. DEVICE PARKED

## 2026-09-20 · uncommitted · feat(core): person advisory caps linear speed (SAF-006)

- 변경: `core_features/safety/manager.py`에 `PersonAdvisory`(present/confidence/observed_at/max_age) + `set_person_advisory`. `clip()`이 신선한 자문에만 전진 상한 0.05 m/s 적용(낮추기만, 선회율 불변). stale/부재/해제는 프로필 복귀. e-stop 경로와 분리
- 증거: `python -m pytest src/core/core/test/test_core_logic.py -q` 27 passed (신규 8건). core 전체 901 passed·10 skipped. flake8 신규 구간 무경고
- gate 변화: 없음. 자문 주입원(YOLO evidence 파이프)은 vision 슬라이스 몫 — 정지 거리 확대는 CommandPolicy 관측 연결 후

## 2026-09-20 · uncommitted · feat(core): DetectionEvidence schema and person injection (D-137 T2)

- 변경: `core_common/protocol/detections.py` 신규 — Detection(정규화 박스)/DetectionEvidence(revision+seq+입력 제원), fresh 300 ms, gap_after, of_label. `safety/manager.py`에 `person_advisory_from` 주입 고리. API Ref §6.1.1 + v1.9 (envelope 1.0 유지)
- 증거: `test_protocol_schemas.py` 15 passed (신규 6건), `test_core_logic.py` 주입 4건, core 전체 919 passed·10 skipped
- gate 변화: 없음. revision 게이트(known-model registry)는 vision 슬라이스 몫

## 2026-09-20 · uncommitted · feat(core): known-model registry gates revisions (D-137 T3)

- 변경: `safety/manager.py`에 `ModelSpec`+`ModelRegistry`(revision+입력 제원 명부, 비어 있으면 fail-closed). `person_advisory_from`에 `registry` 옵션 — 모르는 revision·어긋난 제원은 None. 없으면 옛 동작
- 증거: `test_core_logic.py` 5건 신규(적색→녹색). full suite 타 세션 머지 포함 927 passed·11 skipped
- gate 변화: 없음. D-137 소프트웨어 계약 닫힘 — 남은 것은 vision 실측과 실물 게이트

## 2026-09-20 · uncommitted · feat(vision): D-136 T1 boundary contracts

- 변경: `test_vision_boundaries.py` 2건 (AST import walk + 코드 토큰, 테스트 픽스처 제외, mutation-proven). fleet `test_no_video_relay.py` 2건 (import walk + 라우트 열거, vacuous 방지)
- 증거: 4 passed. core 전체 929 passed·11 skipped, fleet 332 passed·5 skipped
- gate 변화: 없음

## 2026-09-21 · uncommitted · feat(core): gate SLAM mapping and persist maps safely (D-144)

- 변경: runtime backend selects localization or SLAM readiness; mapping start now fails closed until that graph is ready. SaveMap accepts only a safe basename and resolves it below `/var/lib/rosy/maps`, then hashes the generated PGM for the map ID.
- 증거: root plus CORE suite `2018 passed, 24 skipped`; focused readiness, save-map, API, and commissioning contracts pass.
- gate 변화: SOURCE/LOCAL evidence refreshed. ROS-SIM/ARTIFACT/DEVICE remain HOLD pending their actual environments.
- 결정: D-144.
- 교훈: capability advertisement, lifecycle readiness, filesystem scope, and commissioning hashes must describe the same selected backend.

## 2026-09-21 · uncommitted · test(core): make ROS-installed native ARM64 tests deterministic

- 변경: the output-graph fixture now supplies the bridge readiness field explicitly, and the missing-provider test patches entry-point discovery instead of relying on the control package being absent from the environment.
- 증거: native arm64 run 35539577735 reproduced 10 `_readiness` fixture failures and one installed-provider failure after the source build succeeded. Corrected focused tests pass locally; combined root+CORE suite is `2021 passed, 24 skipped` and the native run is repeated after integration.
- gate 변화: none until the repeated native job is green.
- 교훈: a missing-optional-package contract must isolate discovery; installing the optional package must not invert the test's premise.

## 2026-09-21 · uncommitted · refactor(core_api_web): route v1 domain types through api.deps
- 변경: core_api_web v1 라우터 9개 모듈의 core_features 직접 import 12건을 api/deps.py 재수출 면으로 교체(Mode, NavigationError, Dock*, LineFollowMode, valid_costmap_scope, worst, SwarmError, Waypoint). core/test/test_v1_import_boundary.py 2건 추가 — v1 의 core_features 직접 import 금지 + deps 가 타입 면을 소유하는지 검사.
- 증거: 결합도 평가(2026-09-19) §7-5 — features 재조정의 전파 반경이 deps 에서 멈춘다. 텍스트 검사라 rclpy/fastapi 불필요.
- gate 변화: 없음
