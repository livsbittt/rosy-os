## D-7 React + TS + Vite 정적 서빙

**Status:** Superseded by D-75 (2026-09-17)

**Context:** 로봇 로컬 Web UI가 필요하다. 로봇 보드(RPi급) 리소스가 제한적이다.

**Decision:** React 18 + TypeScript + Vite로 개발하고, 빌드 산출물(dist)을 rosy_core가 정적 서빙한다(단일 포트 8080).

**Consequences:** 로봇에 Node 런타임 불필요, 부하 최소화. CI에서 프론트엔드 빌드 파이프라인 필요.

---
