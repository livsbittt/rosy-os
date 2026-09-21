## D-152 CORE 관제의 카메라 표시는 저주기 최신 1장 preview 예외다

**Status:** Accepted (2026-09-21). D-136의 CORE 영상 바이트 전면 금지를 이 좁은
범위에서 대체한다. 대역폭 예산, Fleet 비중계, raw DDS 외부 노출 금지 원칙은
그대로 유지한다.

**Context:** D-150은 CORE `/dashboard`를 유일한 운영 화면으로 정했지만 D-136
제안은 CORE가 영상 바이트를 전혀 만지지 못하게 했다. 그 조합으로는 운용자가
Gazebo 또는 Pinky 카메라가 실제로 보는 차선·횡단보도·정지선·신호 인식 결과를
지도와 한 화면에서 검증할 수 없다. 별도 디버그 `web_node`를 운영 화면으로
승격하면 인증·관제 소유권이 다시 둘로 갈라진다.

**Decision:**

1. Control은 `camera/front`를 인식한 뒤 최대 폭 640, JPEG 품질 72, 기본 2 FPS인
   `camera/preview/compressed`를 만든다. 원본 raw frame은 온보드 내부에 남는다.
2. CORE는 JPEG를 디코딩·인코딩하지 않는다. 최대 512000 bytes를 검증하고 최신
   한 장만 덮어쓰며, 수신 lease 2초가 지나면 제공하지 않는다.
3. Viewer 인증이 필요한 `/api/v1/vision/front/status`와 `/frame`만 추가한다.
   frame은 `no-store`, `Content-Encoding: identity`이고 대시보드는 500 ms status
   poll 중 sequence가 바뀐 경우에만 blob을 가져온다.
4. 이 예외는 MJPEG/WebRTC/RTSP, 녹화, raw image API, 큐, Fleet·Games·상태
   WebSocket 중계로 확장되지 않는다. 영상은 관측 전용이며 정책이나 최종
   `cmd_vel` 권한을 갖지 않는다.

**Alternatives:** 별도 vision HTTP 포트는 운영 인증과 외부 surface를 둘로 나누고
현재 첫 장치 검증에 불필요한 토큰 시그널링을 요구해 기각한다. 디버그 web_node
재사용은 D-150을 되돌리므로 기각한다. raw 또는 base64를 상태 WebSocket에 넣는
방식은 DDS/REST보다 더 큰 팬아웃과 지연을 만들어 기각한다.

**Consequences:** 단일 운용 대시보드에서 지도와 실제 카메라 preview를 함께 볼 수
있다. CORE의 메모리 상한은 한 프레임으로 고정되고 JPEG 재압축 CPU 비용은 없다.
다만 Windows HOST-SIM 스크린샷은 브라우저 경로 증거일 뿐 실제 Gazebo나 Pinky
프레임 증거가 아니며 ROS-SIM/DEVICE gate를 승격하지 않는다.

**Validation / Transition:** JPEG 크기·형식·시각·stale·인증 계약, CORE의 허용된
단일 MIME 예외, Control 2 FPS 압축 wiring, Gazebo opt-in bridge, Chromium의
HOST-SIM 표시를 자동 시험한다. Linux ROS Jazzy에서 source=`GAZEBO`, 장치에서
source=`PINKY` readback을 별도 보존해야 한다.

**Hard limits clarified:** The producer rate is measured with the local
monotonic clock rather than the ROS capture stamp, and both preview DDS ends
use BEST_EFFORT depth 1. Startup rejects settings above 2 FPS, 640 px, or
512000 bytes. CORE requires every JPEG pull to carry the status `sequence`,
limits each authenticated token to at most one successful pull per 400 ms, and accepts
a regressed capture timestamp only after the prior local receipt lease expired
(Gazebo/camera epoch reset). Dashboard reauthentication, page hide, and hidden
tab transitions abort in-flight fetches and revoke the previous blob.

**References:** D-23, D-34, D-47, D-77, D-118, D-136, D-150, D-151.

---
