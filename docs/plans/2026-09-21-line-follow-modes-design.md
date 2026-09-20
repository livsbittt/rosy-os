# IR·카메라 차선 추종 모드 설계

- 날짜: 2026-09-21
- 상태: 승인됨
- 관련 요구사항: NAV-007, SAF-001, SAF-004
- 관련 결정: D-2, D-38, D-47, D-136, D-142, D-143

## 목적

Pinky Pro가 흰색 바닥 차선을 3채널 IR 반사율 센서 또는 전면 카메라로
추종하게 하고, 운용자가 CORE Dashboard에서 한 센서 모드만 선택하도록 한다.
호스트에서는 실제 센서 없이도 동일한 감지·제어 계약을 결정론적으로 재생한다.

## 선택한 구조

차선 인식과 최종 구동 권한을 분리한다. Control은 원시 IR/영상에서
`source`, `visible`, `error`, `confidence`, `stamp`로 구성된 관측만 만든다.
CORE의 `LineFollowManager`는 선택된 소스의 fresh 관측만 소비해 제한된 Navigation
후보 속도를 만들고, 기존 `CommandManager`와 SafetyManager가 최종 `cmd_vel`을
결정한다. 외부 관제는 ROS 토픽을 직접 다루지 않는다.

상위 운전 모드는 새 값을 추가하지 않는다. `IR_LINE`과 `CAMERA_LINE`은
`NAVIGATION` 내부의 배타적 하위 모드다. 일반 Nav2 목표가 시작되거나 운전 모드가
바뀌거나 E-stop이 발생하면 차선 모드는 `OFF`가 되고 보관된 관측과 명령은
폐기된다. 따라서 이전 프레임으로 재출발하지 않는다.

## 감지

IR 모드는 로봇 기준 left/center/right 세 값과 각 채널의 검정·흰색 교정값을
사용한다. 채널별 `black -> 0`, `white -> 1` 정규화 뒤 가중 중심을 계산한다.
흰색과 검정 교정값의 간격이 너무 작거나 값이 비정상인 프로필은 거부한다.
`white_high`를 고정 가정하지 않고 두 끝점의 순서로 극성을 표현한다.

카메라 모드는 기존 NAV-007 하단 ROI 밝은 선 중심 검출을 사용하되 밝기 임계값,
ROI 시작점, 과다 노출 면적, 최소 픽셀을 설정으로 노출한다. 카메라의 기존
장애물 분류와 같은 프레임을 사용해 캡처를 중복하지 않는다. Pi의 Picamera2를
우선 사용하고, 배포 컨테이너에서는 `/dev/video0` V4L2/OpenCV로 fallback한다. 카메라
homography는 거리 보정용이며, 차선 중심 오차 자체의 필수 조건으로 오용하지
않는다.
V4L2 fallback도 settle 이후 auto exposure와 auto white balance를 끈 readback이
확인되기 전에는 camera evidence를 유효하게 만들지 않는다. IR endpoint와 detector
임계값은 배포 호스트의 외부 `line_follow.yaml`로 주입해 이미지 재빌드 없이 로봇별
튜닝할 수 있다.

## 제어와 실패 처리

오차는 `[-1, 1]`이며 양수는 차선이 우측에 있음을 뜻한다. 각속도는 부호를
반전한 비례 제어로 만들고 상한을 둔다. 직선·높은 신뢰도에서는 설정된 순항
속도까지 허용하지만 큰 오차와 낮은 신뢰도에서는 연속적으로 감속한다. 선이
보이지 않거나 관측이 stale/저신뢰이면 즉시 0 속도다. 소실 3초 이후
`nav.lane_lost`를 한 번 발행하며 자동 탐색 주행은 하지 않는다. 재개에는 fresh
관측과 명시적 모드 재선택이 필요하다.
영상 신선도는 브리지 도착 시각이 아니라 `Image.header.stamp`의 원본 캡처
시각부터 계산한다. API와 ROS executor가 같은 manager를 만지는 구간은 잠금으로
직렬화해 전환 직전 소스가 전환 후 명령을 만들지 못하게 한다.
계산된 decision에도 mode generation을 붙여 CORE CommandManager에 기록하는 순간
다시 검사한다. 따라서 tick 뒤 API 전환이 끼어도 이전 소스의 pulse가 남지 않는다.

## 관제와 시뮬레이션

API는 현재 차선 모드/상태/오차/신뢰도/명령/정지 사유를 반환하고 operator가
`OFF`, `IR_LINE`, `CAMERA_LINE`을 선택하게 한다. Dashboard는 세 버튼과 live
상태를 운영 제어 영역에 표시한다.

결정론적 시뮬레이터는 합성 IR 값과 합성 BGR 프레임을 실제 detector에 넣고,
동일한 manager에서 나온 속도를 간단한 차동구동 운동학에 적용한다. 중앙·좌우
오프셋 수렴, 곡선 감속, 센서 stale, 선 소실, 모드 전환 시 zero를 JSON trace로
남긴다. 이는 SOURCE/LOCAL/ROS-SIM 계약 증거이며 실제 바닥 반사율·조명·CSI
지연·모터 방향의 DEVICE/FIELD 검증을 대신하지 않는다.
