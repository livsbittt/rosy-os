# 카메라 배치 실측 설계 — Task 5 (D-52)

- 작성: 2026-09-20. 상태: Draft (실측 전). 관련: D-52, D-47, D-136, D-138,
  `2026-09-13-rosy-os-device-validation-implementation-plan.md` Task 5
- 목적: Picamera2/CSI 캡처를 host service로 둘지 least-privilege container로
  둘지 **같은 시나리오 실측으로** 결정한다. 의견이 아니라 숫자로.

## 1. 비교 대상

| 안 | 캡처 주체 | 장치 전달 | 비고 |
|---|---|---|---|
| H (host) | Pi 호스트 `picamera2` 서비스 | UNIX 소켓/shm으로 `rosy-vision`에 전달 | 호스트가 런타임의 일부가 됨 |
| C (container) | `rosy-vision` 컨테이너 내 캡처 | CSI 노드 + `/run/udev:ro` 바인드 | D-22 방향과 일치 |

CSI 노드는 실명으로 열거하고 별칭(`/dev/rosy-camera`)을 만들지 않는다.
어느 안이든 `rosy-core`는 `/dev`를 받지 않는다.

## 2. 동일 시나리오

- 고정 조건: OV5647, 640x480 BGR8 @10fps, 노출/AWB 고정, 같은 조명·같은 장면
- 각 안 5분 연속 캡처. 측정: 프레임 간격 지터(p50/p95/p99), 드롭율,
  캡처→전처리 완료 latency, Pi CPU% (캡처 프로세스 + 전체), 메모리 RSS,
  under-voltage/throttle 발생 여부 (`vcgencmd`)
- 동시에 CORE stationary 기동 + `cmd_vel` 50Hz 지터 측정 — 캡처가 안전 경로를
  굶기는지가 탈락 조건이다 (D-136 자동킬의 물리 근거)

## 3. 판정 기준 (순서대로)

1. **탈락**: `cmd_vel` deadline miss 발생, 또는 스로틀 발생 시 — 그 안은 폐기
2. **선택**: p99 지터·드롭율·CPU% 낮은 쪽. 차이가 10% 이내면 C (container) —
   readback/서명 경계가 깨끗한 쪽이 이긴다
3. **기록**: 선택 안의 수치를 `camera-profile` 기본값으로 고정 (해상도·FPS·
   latency budget). 미선택 안의 수치는 기각 근거로 보관

## 4. 산출물

- `device-readback` + 측정 CSV (벤치 Pi에서)
- 선택 안의 compose 단편 (device 바인드 목록) — vision 프로필 실체화의 입력
- D-52 후속 ADR (한 줄): 선택 + 수치 + 기각 사유

## 5. 범위 밖

- YOLO 기동 여부 (Hailo 장착 전제, D-137 T5). 본 실측은 캡처+전처리까지만
- H264 인코딩 (MJPEG/정지 JPEG로 측정, D-136)
