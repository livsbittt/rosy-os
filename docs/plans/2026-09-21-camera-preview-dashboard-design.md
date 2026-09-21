# Gazebo/Pinky Camera Preview Dashboard Design

## 목적

`map_260905_update_v2`에서 로봇 전방 카메라가 실제로 본 프레임을 차선·정지선·횡단보도·신호등 판정과 함께 CORE 대시보드에 표시한다. 합성 몽타주나 Gazebo GUI 화면 캡처를 운용 증거로 대체하지 않는다. D-152가 Proposed D-136의 CORE 영상 바이트 전면 금지를 이 bounded latest-frame preview에 한해 대체한다.

## 선택한 구조

Gazebo의 `front_camera_link` 센서와 Pinky의 OV5647은 모두 ROS 상대 토픽 `camera/front`에 원시 `sensor_msgs/Image`를 제공한다. Control의 `road_observer_node`가 이 프레임을 인식에 사용한 뒤, 동일 프레임에 판정 오버레이를 그려 대역폭이 제한된 `camera/preview/compressed` JPEG를 발행한다. CORE의 ROS bridge는 최신 JPEG 한 장만 메모리에 보관하며, 인증된 `/api/v1/vision/front/status`와 `/api/v1/vision/front/frame`으로 제공한다.

대시보드는 Bearer 토큰을 노출하지 않도록 `<img src>`에 토큰을 붙이지 않고 `fetch`로 JPEG blob을 가져온다. 기본 갱신은 500 ms이며, 이전 요청이 끝나기 전에는 다음 요청을 만들지 않는다. 패널에는 출처, 프레임 크기, 캡처 시각, 수신 지연과 stale 상태를 함께 표시한다. 프레임이 없거나 오래되면 마지막 영상을 정상 영상처럼 유지하지 않고 명시적인 HOLD 화면으로 바꾼다.

CORE는 JPEG를 디코딩하거나 재인코딩하지 않고 최대 512000 bytes의 최신 한 장만 통과시킨다. `Content-Encoding: identity`로 이미 압축된 JPEG를 GZipMiddleware가 다시 압축하지 않게 한다. 원시 이미지를 상태 WebSocket, Fleet, Games 또는 기본 다중 로봇 bridge에 싣지 않는다. 영상 표시는 관측 전용이며 교통 정책이나 `cmd_vel` 권한을 갖지 않는다. CORE Command Manager의 단일 최종 명령 권한은 그대로 유지한다.

## 시뮬레이션 연결

단일 Gazebo launch의 opt-in `ros_gz_image` 출력을 `camera/front`로 remap한다. 의미론적 도로 시뮬레이션 launch는 `bridge_image:=true`, 실물 카메라 node 비활성화, `dashboard_source:=GAZEBO`를 사용한다. 실제 Pinky에서는 기존 카메라 node가 같은 `camera/front` 계약을 제공하고 source만 `PINKY`가 된다.

## 리뷰 후 강화된 경계

- 프리뷰 발행 주기는 ROS header stamp가 아닌 로컬 monotonic clock으로
  제한하며, DDS publisher/subscriber는 BEST_EFFORT depth 1만 사용한다.
- 2 FPS, 640 px, 512000 bytes 한계는 보정하지 않고 시작 시점과 인코딩
  결과에서 fail-closed로 강제한다.
- status의 sequence를 frame query에 다시 전달하고 응답 헤더와 비교해
  메타데이터와 JPEG가 같은 프레임을 가리키게 한다.
- CORE는 인증 token별 성공 pull을 400 ms 간격으로 제한한다.
- Gazebo reset 뒤 capture clock이 감소해도 이전 receipt lease가 만료된
  뒤에는 새 epoch로 수용한다.
- 재인증, pagehide, hidden tab에서는 in-flight fetch를 abort하고 기존
  object URL을 revoke해 이전 인증의 영상이 남지 않게 한다.

## 오류 경계

- JPEG가 비어 있거나 제한 크기를 넘으면 저장하지 않는다.
- MIME은 `image/jpeg`만 허용한다.
- 최신 한 장만 보관해 느린 브라우저가 ROS callback을 막지 않게 한다.
- 캡처 시각 역행은 거부한다.
- stale 프레임은 API status에서 명확히 드러내고 frame endpoint는 404를 반환한다.
- 카메라 영상 부재는 주행 안전 판정의 우회 조건이 되지 않는다.

## 검증

ROS-free store 단위 테스트, FastAPI 인증/404/JPEG 헤더 테스트, bridge wiring 계약, Control 오버레이·압축 테스트, 실제 대시보드 브라우저 테스트와 스크린샷을 수행한다. Windows host에서는 Gazebo 렌더 자체를 증명할 수 없으므로 실제 Gazebo 토픽·프레임 증거는 Linux/ROS Jazzy 실행 게이트로 남긴다.
