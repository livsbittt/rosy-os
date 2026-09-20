# 영상 대역폭 예산 실행 계획 — D-136 이행

- 작성: 2026-09-20. 근거 ADR: D-136(Proposed). 선행: D-132(릴레이 순서), D-134(준비 신호 실측)
- 원칙: **영상은 데이터가 아니라 예산이다.** 안전 1Mbps 고정 예약 위에 나머지가 산다.
  검증은 계약 시험 + 실측 — DEVICE/FIELD 주장 금지(D-91)

## 0. 예산표 (N=20 기준, 잠정치 — 실측 후 고정)

| 경로 | 규격 | 대당 | 20대 |
|---|---|---|---|
| gather 스냅샷+메타 | 기존 | ~176kbps | ~3.5Mbps |
| 썸네일+evidence | 160x120 JPEG @1Hz | ~50kbps | ~1.0Mbps |
| on-demand 원본 | 360p pull, token-bucket 대당 1req/5s | 버스트만 | 캡 4Mbps |
| 동시 풀스트림 | ≤2 (운용 규칙, console 강제) | — | ≤4Mbps |
| 안전계 예약 | cmd_vel 50Hz + evidence + heartbeat | — | ≤1Mbps 별도 |

## T1 경로 분리 계약 (LOCAL)

- CORE 영상 바이트 취급 금지 경계 시험: `core` 패키지 import 그래프에
  `cv2/picamera2/ffmpeg` 없음 + `/api/v1` 영상 바이너리 라우트 없음 단언
- gather 경로 이미지 타입 혼입 금지: Fleet 스냅샷 스키마에
  `Image/CompressedImage` 바이트 필드 없음 단언
- Fleet 영상 릴레이 금지: `fleet/server`에 프록시/중계 라우트 없음 단언
- 증거: 호스트 pytest 신규 계약 3건

## T2 예산 캡 + 강등 카운터 (LOCAL → ROS-SIM)

- vision 송출 token-bucket: 평시 썸네일@1Hz + evidence, on-demand pull 레이트리밋
- 버스트 2초 초과 시 자동 강등(원본 → 썸네일-only → 정지) + 강등 카운터 노출
- 영상 큐 depth-1 + 최신 덮어쓰기 고정. RELIABLE 재전송 금지
- 증거: 경계 시험 + ROS-SIM N대 버스트 실측(스냅샷 p95 유지 확인)

## T3 자동킬 + evidence 무효 (ROS-SIM)

- `cmd_vel`/heartbeat deadline miss 연속 N회 또는 점유율 임계 초과 시
  vision/bulk 퍼블리시 자동 차단 → fail-closed(감속→정지)
- vision evidence에 `timestamp + seq + resolution/fps/지연` 메타 필수.
  신선도 >300ms 또는 드롭율 >30%/1s 또는 강제 강등이면 INVALID
- YOLO "clear"로 e-stop 해금 불가 — fresh LiDAR/IR + operator action만
- 미결 상수: deadline 값·miss N회 — 안전 담당과 합의 후 코드 상수로 고정
- 증거: fault-injection 시험(deadline miss 주입 → 킬 확인)

## T4 console 운용 규칙 (Fleet)

- 동시 풀스트림 ≤2: 3번째 요청 큐잉 + 거절 UI
- 우선순위: ALARM > operator_selected > leader > 나머지(메타만)
- FormationSession 중 팔로워 영상 디폴트 차단
- 증거: console 계약 시험 + N대 스냅샷 p95 실측

## T5 실측 후 고정 (DEVICE)

- Pi 5 실측: OpenCV 인코딩 ms/frame + CPU%, H264 HW(V4L2 M2M) 처리량,
  Wi-Fi 실효 대역. Task 5 실기 비교에 포함
- 추론 입력 최소 640 규격은 Hailo 장착 전제. CPU-only면 추론 미기동
- N 상한을 측정 숫자로 문서 고정 (D-131 3단계와 공유)
- H265: 미채택 유지 (HW 인코더 부재)

## 순서·종료 조건

- T1 → T2 → T3 → T4 → T5. T3의 deadline 상수는 합의 없이 코드에 넣지 않는다
- 종료: 계약 시험 녹색 + ROS-SIM 버스트 실측 + D-136 Status → Accepted
- 범위 밖: YOLO advisory 서열 ADR(다음), 모델 generation 바인딩, RTSP/WebRTC (요구 생길 때)
