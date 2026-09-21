---
module: fleet/server
tags: [silent-failure, auth, server-guard, ui-contract, partial-testing]
problem_type: workflow_issue
applies_when: 서버에 guard(토큰·역할·CSP)를 켜거나 강제하는 코드를 고칠 때, 그 guard가 실제 클라이언트(특히 자사 UI)와 맞물리는 경로를 검증할 때
---

# 서버 guard 시험은 guard만 보고 클라이언트를 안 본다 — 토큰을 켜면 UI가 조용히 죽는다

`fleet console` 서버는 루프백 밖 바인드에 운영자 토큰을 강제한다(`cli.run_console`,
`app.authorize`). `test_server_app.py::test_console_token_guards_the_site_api`는 이 가드를
정확히 못박아 둔다 — 토큰 없으면 401, `Authorization: Bearer`와 함께면 200. 시험은 초록이었다.

그런데 정작 이 서버가 서빙하는 관제 UI(`web/console.js`)의 `call()`은 어떤 헤더도 붙이지
않았다. 토큰을 켜는 순간 — 즉 관제타워처럼 루프백 밖으로 여는 바로 그 구성에서 — 화면의 모든
폴링이 401로 막히고 상단 pill은 "Fleet 서버 없음"을 보인다. 서버는 살아 있고 API 시험도
초록인데, 사람이 보는 화면은 아무것도 못 받는다.

## 교훈

1. **guard 시험은 "요청이 거절되는가"만 본다.** "우리 클라이언트가 통과하는가"는 별도의
   경로다. guard를 켜는 코드(바인드, 역할, CSP)를 고칠 때는 그 guard와 맞물리는 실제
   클라이언트 — 여기서는 자사 UI — 의 요청을 한 번은 실어 보라.
2. **가능하면 headless라도 실제 순서를 재현하라.** 이 결함은 curl 한 줄(토큰 없는 state
   요청 → 401 → 브라우저라면 여기서 끝)과 "UI가 보내는 헤더가 무엇인가"를 대조하면
   바로 보였다. 브라우저가 없어도 요청 순서(state → estop → map)를 흉내 내면 된다.
3. **"서버 없음"이라는 UI 문구가 거짓말을 했다.** 401과 연결 실패를 같은 catch에서
   접어 버리면 운영자는 원인을 서버 죽음으로 오독한다. 인증 실패는 인증 실패로
   말하게 분리하라 — 수정은 401일 때 "토큰 필요" 상태를 따로 표시한다.
4. 클라이언트 쪽 시험이 없는 UI 자산(CSP 때문에 프런트 테스트 인프라가 없는 이 저장소)은
   최소한 `node --check` 수준의 문법 검증 + API 레벨 E2E 재현으로 비켜라.

## 적용

- 이 저장소에서 토큰/역할 가드를 다루는 곳: `core`의 `deps.py`(SEC-101), `fleet`의
  `app.authorize`. 어느 쪽이든 "가드 시험"과 "클라이언트 시험"을 한 쌍으로 둔다.
- UI가 인증을 다루게 되면 토큰 보관 위치도 계약이다: 이 수정은 `sessionStorage`만 쓴다 —
  공유 관제PC에서 `localStorage`는 다음 근무자에게 운영자 토큰을 물려준다(D-30 정신).
