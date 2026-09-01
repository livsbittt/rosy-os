# Rosy OS Dashboard Design

## 목적과 범위

Rosy OS Dashboard는 Raspberry Pi OS 위에서 실행되는 `rosy_core`의 현장 운영 화면이다. 별도 Node.js 서버나 프론트엔드 런타임을 두지 않고 FastAPI가 `/dashboard`와 정적 자산을 직접 제공한다. 첫 화면에서 작업자는 로봇 연결 상태, 모드, 비상정지, 자세·속도·배터리, 기능 가용성, 최근 이벤트와 Raspberry Pi의 CPU·메모리·디스크·온도·업타임을 확인한다. 기존 역할 기반 토큰으로 데이터와 제어 권한을 분리하며 토큰은 브라우저 `sessionStorage`에만 저장한다.

대시보드는 읽기 중심이다. 로봇의 모드 변경과 비상정지는 기존 API를 그대로 호출하지만, 임의 셸 명령·패키지 업데이트·네트워크 변경·호스트 재부팅은 제공하지 않는다. 컨테이너가 호스트 root 권한을 갖지 않는 기존 `rosy-core`/`rosy-io` 경계를 유지하기 위해서다. Raspberry Pi OS 정보는 `/host` 아래에 읽기 전용으로 마운트한 `/proc`·`/sys`·`/etc` 파일을 통해 수집하고, 네이티브 실행 시에는 실제 `/`를 읽는다. 값을 읽지 못하면 API는 실패하지 않고 해당 필드를 `null`과 상태 사유로 반환한다.

시각 방향은 어두운 산업용 계기판과 종이 작업지시서의 조합이다. 장식보다 상태 대비를 우선하고, 정상·주의·위험을 색상뿐 아니라 문구와 형태로 함께 표현한다. 외부 폰트와 라이브러리를 사용하지 않으며 단일 HTML, CSS, ES 모듈 JavaScript로 구성한다. 상태 WebSocket이 끊기면 REST 폴링으로 자동 전환하고, OS 정보는 낮은 빈도로 갱신하여 Pi 부하를 제한한다.

## 데이터 흐름과 안전 경계

1. 브라우저가 `/dashboard`를 로드한다.
2. 사용자가 viewer/operator/admin 토큰을 입력한다.
3. `/api/v1/system/runtime`, `/system/info`, `/system/capabilities`, `/robot/state`, `/safety/state`, `/events`를 조회한다.
4. `/ws/state`를 연결해 로봇 상태를 갱신하며 실패 시 2초 REST 폴링으로 전환한다.
5. 제어 버튼은 기존 `/mode`, `/safety/stop`, `/safety/release`만 호출한다.
6. 모든 위험 동작은 확인 절차와 서버 역할 검사를 모두 거친다. 모드 변경은 요청 중 재입력을 잠그고, NAV는 capability가 활성화된 경우에만 표시·허용하며, 서버는 진입 전에 오래된 navigation twist를 제거한다.
