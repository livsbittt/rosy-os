# YOLO 자문 서열 실행 계획 — D-137 이행

- 작성: 2026-09-20. 근거 ADR: D-137(Proposed). 선행: D-136(대역폭 예산)
- 원칙: **YOLO는 자문역이다.** 결정은 LiDAR/IR가 하고 영상은 증거만 낸다.
  모델 올리기 전에 서열 계약을 먼저 잠근다

## T1 서열 계약 (LOCAL)

- CORE 정책 스냅샷에 YOLO advisory 입력 자리만 둔다. 단독 정지 경로 없음 단언
- `vision/detections` 단일 발행자 고정. 이중 발행은 결함
- e-stop 해금 경로에 vision 없음 단언 (fresh LiDAR/IR + operator action만)
- 증거: 호스트 pytest 계약 4건

## T2 DetectionEvidence 스키마 (LOCAL)

- `DetectionEvidence`: class, bbox 정규화, conf, stamp, seq, model rev,
  입력 규격/fps/지연 메타. immutable 스냅샷
- CORE 후보별 재평가 + stale 폐기. control `TrackedEvidence` 패턴 재사용
- "못 본 것"(seq gap)과 "없는 것"(빈 detections)을 구분
- 증거: 순수 로직 시험 (rclpy 없이)

## T3 모델 generation 바인딩 (LOCAL)

- 가중치 버전·digest·입력 규격을 D-47 패턴으로 관리
- unknown revision fail-closed. 모델 교체 = generation 전이 + rollback
- 증거: revision 불일치·롤백 시험

## T4 트리거 게이트 (ROS-SIM)

- YOLO 단독 버스트 트리거 불가. 전송 조건 = corroboration 또는 operator 요청
- 거짓음성 주입: 깨진 영상 + LiDAR 장애물 → 정지 유지 확인
- 오탐 폭주율 상한 합의 (분당 FP — 안전 담당과 수치 확정)
- 증거: fault-injection 시험

## T5 온보드 기동 조건 (DEVICE)

- Hailo 장착 전제. CPU-only면 추론 미기동 (`vision.enabled: false` 유지)
- 추론 입력 최소 640 규격 @≥8fps 실측 확인
- Pi 5 CPU/메모리/송출 상한 보증 + 자발적 강등 순서 (해상도→fps→정지)
- 증거: DEVICE 실측 (Task 5 실기 비교에 포함)

## 순서·종료 조건

- T1 → T2 → T3 → T4 → T5. 코드는 T2 스키마부터, 노드 기동은 T5까지 금지
- 종료: 계약 시험 녹색 + ROS-SIM 주입 실측 + D-137 Status → Accepted
- 범위 밖: 모델 선정·학습, RTSP/WebRTC, Fleet 영상 (D-136이 이미 제외)
