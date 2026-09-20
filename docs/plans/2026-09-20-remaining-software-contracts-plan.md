# 잔여 소프트웨어 계약 실행 계획 — 실물 전 (D-136/D-137/NAV-007)

- 작성: 2026-09-20. 상태: in_progress (P1 done). 관련: D-136, D-137, D-139, NAV-007, SAF-006
- 원칙: **실물 없이 닫히는 것만 한다.** 카메ra placement, Pi 게이트, 실물 도크,
  YOLO 실측은 범위 밖 — D-139가 잠근다. ROS-SIM Gazebo 브리지는 D-83 세션 몫.

## P1. D-136 T1 계약 테스트 (LOCAL)

- CORE 영상 바이트 취급 금지: `core` import 그래프에 `cv2/picamera2/ffmpeg`
  없음 + `/api/v1` 영상 바이너리 라우트 없음 단언
- gather 경로 이미지 혼입 금지: Fleet 스냅샷 스키마에 이미지 바이트 필드 없음
- Fleet 영상 릴레이 금지: `fleet/server`에 프록시/중계 라우트 없음
- 증거: 호스트 pytest 신규 3건, 적색→녹색

## P2. 차선 조향 소비 (LOCAL)

- `LaneObservation.error → 각속도` pure 함수 (`lane.py` 옆, ROS-free)
- 0.10 m/s 캡 상수 재사용, `nav.lane_lost` 방출점 정의
- 노드 배선(카메라→함수→명령)은 카메라 온 뒤 — evidence까지 닫힌 상태 유지
- 증거: control 스위트 신규 계약 (조향 부호·포화·상실-정지)

## P3. D-137 T4 fault-injection (LOCAL, 반쪽)

- 깨진 영상 + LiDAR 장애물 → 정지 유지. person advisory 경로는 준비됨
- LiDAR 쪽 person 입력이 control 정책에 없어 반쪽 — YOLO 파이프까지 대기
- 가능한 만큼만: stale evidence INVALID 전이 시험

## 범위 밖 (실물·타 세션)

- D-136/D-137 Accepted 전환 (실측 필요)
- 카메라 placement, Pi 서명/readback, 실물 도크 (설계済み, 실행 대기)
- Gazebo 브리지 (D-83), 하네스 re-stamp (타 세션 흐름)

## 순서·종료 조건

- P1 → P2 → P3. 각 항목 적색→녹색 + 회귀 후 커밋
- 종료: 3건 착지 후 본 계획 Status → complete
