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

## FP 폭주율 상한 제안 (미확정 — 안전 담당 서명 대기)

T4의 corroboration 게이트는 패킷당 판정이라 시간축 방어가 없다 — corroborated
1초/noncorroborated 1초 플래핑이 버스트 시작을 연속 유발할 수 있다. 상한이
묶어야 하는 것은 **버스트 시작 빈도**다. 유지·동시수는 이미 D-136이 결정했다:

| 이미 결정 (D-136) | 값 |
|---|---|
| on-demand pull | token bucket 1req/5s/대 |
| 동시 풀스트림 | ≤2 (3번째는 큐잉/거절) |
| bulk 채널 | 2Mbps, 안전 트래픽 선점 |

**제안**: corroborated 버스트 **시작 최소 간격 30s/소스**, 분당 시작 ≤2회(전자의
부수 효과로 자동 충족). 근거 — 사람 통과 1회(≈20–30s, 자문 캡 0.05 m/s 크롤)에
버스트 1회 시작이면 충분하고, 30s 간격이면 플래핑 주기(≈1s)를 흡수한다. 위반
시 버스트 시작 거절 + 거절 카운터 노출(D-136 §6 버림 카운터 패턴과 동일).
구현 위치는 송신 측 토큰 버킷(`burst_gate`는 패킷당 판정만 유지).
**검증**: T4 Gazebo 종단에서 corroborated/noncorroborated 교대 플래핑 주입 →
시작 간격이 30s 미만으로 뛰지 않음을 확인.

- [ ] 안전 담당 서명 (수치 확정 시 이 섹션을 ADR 수치로 승격)

## 순서·종료 조건

- T1 → T2 → T3 → T4 → T5. 코드는 T2 스키마부터, 노드 기동은 T5까지 금지
- 종료: 계약 시험 녹색 + ROS-SIM 주입 실측 + D-137 Status → Accepted
- 범위 밖: 모델 선정·학습, RTSP/WebRTC, Fleet 영상 (D-136이 이미 제외)

## 진행 기록

- 2026-09-20: T2 스키마(`core_common/protocol/detections.py`) + T3(`ModelRegistry`) + CORE 주입 고리(`person_advisory_from`·`set_person_advisory`) 착지 (07d5da3)
- 2026-09-21: T2 보강 — control 생산 측 스냅샷(`control.control.detection_evidence`), `inference_ms`(API Ref v1.11 additive), D-18 동기·박스 규칙 일치 시험
- 2026-09-21: T1 완료 — 서열 계약 4건(`TestD137SequenceContract`): advisory 상한 전용·estop 불가·해금 무 vision·`vision/detections` 무발행 게이트. 변이 증명 3건
- 2026-09-21: T4 순수 조각 — 버스트 게이트(`control.control.burst_gate`: operator 또는 corroboration만 허용, vision 단독 거절, 변이 증명), 주입 시임(`core_features.safety.manager.PersonAdvisoryFeed`: broken/stale/gap 패킷 → 자문 해제, 어떤 입력에도 예외 없음, e-stop 무관, 변이 증명). 회귀: Windows core 980 passed, WSL Jazzy 979 passed(cv2 4.6 `generateImageMarker` 환경 실패 1건 — 본 변경 무관)
- 2026-09-21: T4 와이어 구간 — `ros_bridge`에 `detection_evidence` 구독(D-136 §2 분리 채널) + `services`가 `PersonAdvisoryFeed` 소유 + **WSL Jazzy 실 rclpy 그래프 주입 시험 통과**(발행→좌석 캡·깨진 패킷→프로필 복귀·e-stop 불변, 브리지 구조 핀 9건 포함 10 passed). 그래프 시험이 시계 기준 실결함 발견: 좌석 stamp는 ROS epoch, `clip` 판정은 monotonic — `PersonAdvisoryFeed`가 캡처 시 나이만 좌석 시계로 옮기는 TrackedEvidence 패턴으로 수정
- 2026-09-21: T4 fault-injection 구성 증명 — `TestD137MetricStopComposition`(호스트 rclpy 불요): Control 정책 obstacle 정지(출력 0) 상태에서 사람 자문이 좌석에 살아 있어도 정지 유지, 깨진 영상( invalid_packet ) 후에도 정지 유지·프로필 복귀, vision이 만든 정지·해제·e-stop 모두 없음. 회귀: Windows 1027 passed·12 skipped, WSL Jazzy 1038 passed(cv2 4.6 환경 실패 1건 불변)
- 남음: T4 Gazebo 상 fault-injection 실측(깨진 영상 + LiDAR 장애물 → 정지 유지 — 순수/그래프 계약은 모두 녹색, SIM 종단만 남음), FP 폭주율 수치 합의(분당 FP — 안전 담당), T5 DEVICE 실츱(Hailo). D-137 Status 전환은 종료 조건 충족 후
- SIM 환경 실태(2026-09-21 조사·갱신): WSL Ubuntu에 Gazebo Sim 8.15.0 — **헤드리스 서버 부팅 검증(`gz sim -s` exit 0)**. 병렬 세션의 `~/rosy_ws` SIM 스택 빌드 **완료**(rosy_bringup·rosy_core·rosy_description·rosy_fleet·rosy_gz_sim 등, 활성 빌드 프로세스 없음). 단 `ros_gz` 파이썬 모듈은 부재(C++ 브리지 라이브러리 16종은 존재) — 실측 시 `apt install ros-jazzy-ros-gz` 확인. 오버레이 `install/setup.bash` 소싱이 PYTHONPATH를 덮어쓰는 사례 확인 — 언더레이(/opt/ros) 소싱 후 파이썬 경로는 append로 재구성할 것
