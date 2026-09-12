# ROSY Flask 동등성 체크리스트 (P0-7, D-3)

> **Status: Historical parity baseline.** Flask was replaced by the Rosy OS
> FastAPI surface under D-3. Keep this checklist for migration traceability;
> current implementation and Device validation are tracked in
> `docs/plans/2026-09-13-rosy-os-device-validation-implementation-plan.md`.

**Document ID:** ROSY-PLN-CHK-001
**기준:** 구 Flask `rosy_navigation/scripts/nav2_web_server.py` (560줄) vs 신규 `rosy_core` FastAPI `/api/v1` (ROSY-API-REF-001)
**완료 기준:** 아래 전 항목 PASS 시 P1-13 (Flask 런치 제거) 착수 가능.

> 레거시 경로(`/api/state` 등) 호환은 유지하지 않는다(D-3). 기존 워크플로는 신규 API로 전환한다.

## 1. 엔드포인트 매핑

| # | Flask (구) | Rosy API (신) | 동등성 기준 (수용 기준) | 상태 |
|---|---|---|---|---|
| E-1 | `GET /api/state` — TF pose·map·path·costmap 통합 스냅샷 | `GET /api/v1/robot/state` + `GET /api/v1/map` + `GET /api/v1/navigation/path` + `GET /api/v1/map/costmap` | 4개 엔드포인트 조합으로 구 응답의 pose(x,y,yaw)·OccupancyGrid·Path·Costmap 필드 전부 재현. 좌표값은 TF(map→base) 기준 동일 | API (단위). 실기 OccupancyGrid E2E 잔여 |
| E-2 | `POST /api/goal` — NavigateToPose 전송 | `POST /api/v1/navigation/goal` | `{x,y,yaw}` 동일 payload로 Nav2 목적지 도달. + waypoint 이름 지원(WPT-003)·map_id 검증(MAP-002)은 추가 기능 | API |
| E-3 | `POST /api/initialpose` — AMCL 초기 자세 | `POST /api/v1/localization/initialpose` | 동일 payload로 AMCL 초기화 후 pose 수렴 | API |
| E-4 | `GET /api/nav/status` — 주행 상태 | `GET /api/v1/navigation/state` (+ `/ws/state` 실시간) | NAV-004 7상태로 매핑(구: 진행중/대기 등 이분법 → 신: 세분화). 구분할 수 없는 상태 없음 | API |
| E-5 | `POST /api/nav/stop` — 취소 | `POST /api/v1/navigation/cancel` | 주행 중 취소 → 로봇 정지 + 상태 `CANCELED` + `nav.canceled` 이벤트(EVT) | API |
| E-6 | `POST /api/slam/reset` | `POST /api/v1/slam/reset` (+ 세션 API `slam/start`·`stop`, NAV-005) | 매핑 세션 리셋 후 신규 스캔 정상 누적 | **hollow** — 라우트는 있으나 리셋은 없다. `RosBridge` 에 `reset_mapping` 구현이 없어 200 만 돌려주고 있었고, D-32 로 정직한 501/400 이 되었다. 실물 slam_toolbox `Reset` 이식은 `mapping/` 트리거 대기 |
| E-7 | `POST /api/slam/save_map` | `POST /api/v1/slam/save` | 맵 파일 저장 + 응답 `map_id`(MAP-001, D-13). 저장 맵으로 Nav2 재시작 시 주행 가능 | API |

## 2. 비-엔드포인트 동등성

| # | 항목 | 기준 | 상태 |
|---|---|---|---|
| N-1 | 맵 저장 위치 | 구와 동일한 디렉터리(`rosy_navigation/map/`) 호환 또는 마이그레이션 스크립트 | ☐ |
| N-2 | use_sim_time | 시뮬(gz)·실물 양쪽에서 동작 (gz_multi + gz_web_* 워크플로 대체) | ☐ |
| N-3 | 오류 응답 | 구의 ad-hoc 오류 → 표준 `{error:{code,message,detail}}` (ERR-101) + 주요 케이스 코드 매핑 | ☐ |
| N-4 | HTML 페이지 (`index.html`) | rosy_core가 서빙하지 않음. rosy_web(M2) 완성 전까지는 API 테스트로 대체 — 동등성 대상 아님(예외 항목) | ☐ |

## 3. 시험 절차

1. 실물 또는 gz 시뮬 1대 기동 (`rosy_core.launch.py mode:=nav|slam`)
2. E-1~E-7 순서대로 curl/스크립트 실행, 응답 스키마를 OpenAPI(계약)와 대조
3. 맵빌딩 → 저장 → 주행 E2E 1사이클 완주 (구 워크플로 대체 확인)
4. 전 항목 PASS → Flask 런치(web_nav2/web_slam) 제거 (P1-13), M2 후 스크립트 삭제

| 일자 | 실행자 | 결과 | 비고 |
|---|---|---|---|
| — | — | — | — |
