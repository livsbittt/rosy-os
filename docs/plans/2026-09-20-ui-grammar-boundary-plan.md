# UI 문법 경계·스타일가이드 실행 계획 — D-129·D-130 이행

- 작성: 2026-09-20
- 근거 ADR: D-129(Proposed — 이행이 착지해야 Accepted), D-130(Accepted, 방향)
- 검증 원칙: ROS가 필요 없는 호스트 pytest만. DEVICE/FIELD 주장 금지(D-91). 스위트는 별도 호출(D-128)

## Task 1 — CORE `/ui` 라우트와 자산 고정 (D-129.1, D-130.3)

- core_api_web: `GET /ui/tokens.css` — 웹 패키지의 tokens.css를 동일 출처로 서빙
- 파일 SHA256을 기동 때 기록하고, 릴리스 핀 불일치는 경고로 남긴다(D-130.3)
- 소유: core_api_web. 증거: 자기 시험에 라우트·본문 일치 단언 추가

## Task 2 — fleet 전환 (D-129.2·4)

- `fleet console`에 `--ui-tokens <path>` — launch/compose가 share 경로를 주입하고 fleet은
  ROS import 금지를 유지한다(D-126 선례)
- asset allowlist에 tokens 항목을 추가하고 본문은 설정 파일을 그대로 서빙한다
- fleet 자체 tokens.css 사본은 삭제한다. `test_console_palette`는 시트 게이트(별칭 선언 0,
  간격은 `--space-*`)를 유지하고, 삭제 사본을 읽던 값 게이트는 제거한다 — 값 게이트 소유는
  단일 파일을 읽는 CORE다(D-82)
- `/console` 페이지는 `/ui/tokens.css`를 링크한다(동일 출처 — CSP `style-src 'self'` 유지)
- 증거: `python -m pytest src/site/fleet/test -q`

## Task 3 — 스타일 갤러리 `/styleguide` (D-129.3)

- CORE가 손으로 쓴 정적 페이지로 어휘 표 열 컴포넌트를 규칙·게이트 이름과 함께 렌더링한다
- 갤러리 스타일시트는 토큰 재선언 0, 간격·글자는 스케일만 — 기존 게이트를 그대로 적용
- 증거: `test_styleguide.py` — 열 이름 정확 렌더링, 날 색상 없음
- 설계만인 넷(D-92 (a)~(d))은 갤러리에도 만들지 않는다

## Task 4 — 문법 분리 게이트 (D-130.1)

- fleet: `test_grammar_separation.py` — 콘솔 관용구 금지 목록(고정 레일·region 3분할·카드
  윤곽 클래스), 스타일시트 참조는 자기 것과 `/ui/tokens.css`뿐
- core 콘솔: 기존 레이아웃·토큰 게이트가 이미 소유한다 — 추가 없음
- games: 자기 UI가 어휘를 채택할 때 따라온다(지금 아님)

## Task 5 — 상태 전이와 기록

- Task 1–3이 녹색이면 D-129를 Proposed→Accepted로(색인·본문·progress)
- Task 4는 D-130 효력의 착지다
- 각 Task 후 logs.md 항목 추가 + index 재생성
