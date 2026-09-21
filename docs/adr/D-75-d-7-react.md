## D-75 로봇 로컬 화면은 손으로 쓴 정적 자산이다 — D-7 React 대체

**Status:** Accepted (2026-09-17). D-7을 대체한다. concept 16, D-72.

**Context:** D-7(2026-08)은 로봇 로컬 Web UI를 React 18 + TypeScript + Vite로
개발하고 `dist`를 정적 서빙하기로 했다. D-23(2026-09-01)은 그 뒤에 "별도
React/Node 서비스는 첫 Pi 5 런타임의 프로세스·배포·장애 표면을 늘린다"며
FastAPI가 로컬 HTML/CSS/JavaScript 자산을 직접 제공하도록 결정했고, 실제
구현이 그 길로 갔다. 저장소에 `package.json`도 번들러도 없고 `/dashboard`는
손으로 쓴 ES 모듈을 서빙한다. 그런데 **D-7의 Status가 Accepted로 남아 있어
두 Accepted ADR이 서로 모순**이고, 어느 쪽이 유효한지 문서만 보고는 알 수
없다. D-72 이행 계획이 이 모순 위에서 레이아웃과 렌더러를 손보게 되는데,
D-7을 나중에 이행하면 그 산출물이 폐기된다.

**Decision:** D-7을 Superseded로 표시하고, 로봇 로컬 화면은 **빌드 단계 없는
손으로 쓴 정적 자산**임을 확정한다.

- `rosy_core`가 `web/`의 HTML·CSS·ES 모듈을 직접 서빙한다(D-23).
- 번들러·npm·Node 런타임·외부 CDN·웹폰트를 도입하지 않는다.
- 전송 경량화는 빌드가 아니라 응답 압축으로 한다.
- 색의 단일 출처는 `web/tokens.css`이며 계약 시험이 지킨다(D-72).

**Alternatives:** D-7을 이행해 Vite로 전환하는 안은 Pi 5 로봇 보드에 빌드
파이프라인과 배포 산출물 검증을 새로 얹고 D-23이 줄인 장애 표면을 되돌린다.
두 ADR을 그대로 두는 안은 모순을 남겨 다음 사람이 같은 질문을 다시 한다.

**Consequences:** 프론트엔드 작업은 빌드 산출물이 아니라 소스가 곧 배포물이라는
전제로 한다. 손으로 쓴 자산이므로 규율은 도구가 아니라 계약 시험이 만든다.
React 도입이 필요해지면 이 ADR을 먼저 뒤집어야 하며, 그때 Pi 이미지·서명·
digest 경로를 함께 설계한다.

**Validation / Transition:** `src/rosy_core/test/test_dashboard_no_bundler.py`.
`package.json`/`vite.config.*` 없음. `/dashboard` allowlist는 `api/app.py`.
색 단일 출처는 D-72 시험이 맡는다.

**References:** D-7, D-22, D-23, D-72,
[concept 16](../concept/16_ROSY_Interface_Design_Principles.md),
[이행 설계](../plans/2026-09-17-interface-design-implementation-design.md).
---
