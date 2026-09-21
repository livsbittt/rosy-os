## D-23 Rosy OS 화면: FastAPI 내장 대시보드 + 읽기 전용 호스트 텔레메트리

**Status:** Accepted (2026-09-01)

**Context:** Raspberry Pi OS에서 `rosy_core`를 운영하려면 로봇 상태뿐 아니라
CPU, 메모리, 저장소, 온도와 런타임 오류를 현장에서 확인할 화면이 필요하다.
별도 React/Node 서비스는 첫 Pi 5 런타임의 프로세스·배포·장애 표면을 늘린다.
반대로 core 컨테이너에 Docker socket, host root 또는 systemd 제어 권한을
주면 D-22의 Core/I/O 최소권한 분리를 훼손한다.

**Decision:** FastAPI가 `/dashboard`와 로컬 HTML/CSS/JavaScript 자산을 직접
제공한다. 로봇 상태와 제어는 기존 인증된 REST/WebSocket 계약을 재사용한다.
호스트 상태는 `/proc` 핵심 파일, `/sys/class/thermal`과 그 심볼릭 링크 대상인
`/sys/devices/virtual/thermal`, `/etc/os-release`,
`/etc/hostname`만 개별 read-only mount하여 수집한다. 임의 셸 실행, host root,
Docker socket, systemd 제어 및 OS 설정 변경은 대시보드 범위에서 제외한다.

**Consequences:** 별도 프론트엔드 런타임 없이 오프라인 현장 화면을 제공하고
기존 API 역할·감사 경계를 유지한다. host 파일이 없거나 플랫폼이 다르면 일부
값은 `unavailable`로 표시된다. 향후 네트워크·업데이트·재부팅을 제어하려면
별도 최소권한 host agent와 명시적인 명령 계약을 새 ADR로 설계해야 한다.
모드 변경은 UI 확인과 중복 요청 잠금을 거치며 서버가 capability를 재검사한다.
내비게이션 속도 표본은 500 ms 뒤 만료되어 stale 명령 재생을 막는다.

---
