# ROSY P1 통합 테스트 리포트

**Document ID:** ROSY-PLN-RPT-001
**Version:** v1.0 (2026-08-29)
**대상:** rosy_core P1 1~2차 스프린트 (ROSY-PLN-001 Phase 1)
**환경:** ROS 2 Jazzy (Ubuntu 24.04, WSL2), pytest 7.4 / FastAPI TestClient / 실기동 스모크

---

# 1. 요약

| 구분 | 결과 |
|---|---|
| 단위/통합 테스트 (pytest) | **40/40 통과** (1차 30 + 2차 10) |
| 실기동 스모크 (rosy_core 실행 + curl/WS) | **전 항목 통과** (§3) |
| 빌드 (colcon, 11 패키지) | 통과 |

테스트가 검출한 결함 5건(모두 수정·재검증): ① 조회 API 인증 누락 ② `setup.cfg` `$base` 변수 확장으로 실행파일 `/lib` 미설치 ③ rclpy `Node.services` 속성 충돌 ④ `api/v1/__init__.py` 누락(미설치) ⑤ rclpy 로거 printf 인자 미지원.

# 2. 단위/통합 테스트 상세 (40건)

| 영역 | 파일 | 주요 검증 | 요구사항 |
|---|---|---|---|
| 프로토콜 스키마 | test_protocol_schemas.py (7) | envelope 기본값·왕복 직렬화, 이벤트 seq, 스냅샷 기본값, swarm additive 필드·pose 스트림 | P1-19, D-10, D-20 |
| 중재/모드머신 | test_core_logic.py (6) | 미등록 소스 거부, MANUAL↔NAV 상호차단, EMERGENCY 전이 제약 | CMD-001, §8.1 |
| cmd_vel 멀렉서 | test_core_logic.py (5) | 워치독 만료 zero, E-Stop 전량 차단, 속도 클리핑 | SAF-001/002/004, D-2 |
| 안전 정책 | test_core_logic.py (2) | E-Stop 이벤트·중복 무시, 배터리 임계 통과 1회 | SAF-001/005 |
| 이벤트 버스 | test_core_logic.py (2) | seq 단조, 링 버퍼 | EVT-003/004 |
| Waypoint | test_core_logic.py (1) | CRUD·중복 거부·영속화 | WPT-002, D-9 |
| Navigation | test_core_logic.py (3) | waypoint 목표, MAP_MISMATCH, 수명주기 이벤트, stuck 자동취소 | NAV-001/002/006, MAP-002 |
| API (1차) | test_api.py (7) | 인증 3롤·401/403, teleop 흐름, E-Stop 사이클, ERR-101 형태 | SEC-101, ERR-101 |
| 센서 스토어 | test_sprint2.py (1) | set/get, 미수집 404 | §12 |
| 진단 수집기 | test_sprint2.py (4) | provider 예외→ERROR, worst 순서, 신선도, 실 disk | DIAG-001/002 |
| SLAM 세션 | test_sprint2.py (2) | 세션 중 Goal 거부→save→map_id 갱신→무세션 save 거부 | NAV-005, MAP-001 |
| API (2차) | test_sprint2.py (3) | /sensors, /slam 흐름, /metrics Prometheus 형식 | §12, NAV-005, OBS-101 |

# 3. 실기동 스모크 (로컬 ROS 2 Jazzy, 하드웨어 없음)

실행: `ros2 run rosy_core rosy_core` → API 8080 / cmd_vel 50 Hz 게시 확인 (~86 Hz 계측)

| # | 시나리오 | 결과 |
|---|---|---|
| S-1 | 부팅 → `system/info` (IDN-003: robot_id/모델/ROS 버전/IP) | PASS |
| S-2 | `robot/state` 스냅샷 (mode/navigation/online) | PASS |
| S-3 | MANUAL 진입 → teleop 스트림 → `/cmd_vel` linear=0.05/angular=0.1 반영 | PASS (§8.1, D-2) |
| S-4 | teleop 스트림 정지 0.7s → cmd_vel 자동 zero | **PASS — SAF-002 실증** (AT-06 상당) |
| S-5 | E-Stop → cmd_vel 0.0·상태 반영 → release 복귀 | PASS (AT-12 상당) |
| S-6 | Waypoint 생성 201 + 목록 | PASS (WPT-002) |
| S-7 | 이벤트 로그 (boot/mode.changed/safety.*) | PASS (EVT) |
| S-8 | WS `/ws/state` seq 단조 증가 | PASS (API-102) |

# 4. AT 달성 현황

| 시험 | 상태 | 근거 |
|---|---|---|
| AT-03 (ID/상태 조회), AT-12 (API E-Stop), AT-14 일부, AT-15 일부, AT-16 | **API 레벨 통과** | S-1/2/5/7 + 단위테스트 |
| AT-05/06 (Joystick/워치독) | 로직·cmd_vel 레벨 통과 | S-3/S-4 (UI는 M2) |
| AT-01 (systemd 자동실행) | 준비 완료 — 실기기 설치 잔여 | deploy/rosy-core.service + install.sh |
| AT-02/04/07~11/13 | 실기기/시뮬 M2~M3 대상 | — |

# 5. 잔여 리스크

- Nav2 NavigateToPose 실행기·slam_toolbox SaveMap 연동은 **실환경(시뮬/실물) 미검증** — 로직은 executor 인터페이스 뒤 단위테스트로 검증됨. M0/M3 시험에서 확인 필요
- cmd_vel 계측 주기 ~86 Hz (타이밍 특성, 무해하나 관찰 지속)
- /metrics 인증 면제 — 배포 정책(SEC-102) 확인 후 필요시 토큰 적용
