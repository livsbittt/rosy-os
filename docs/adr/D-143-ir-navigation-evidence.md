## D-143 IR·카메라 차선 추종은 NAVIGATION 내부의 배타적 evidence 소스다

**Status:** Accepted (2026-09-21). 실행 계획:
`docs/plans/2026-09-21-line-follow-modes.md`.

**Context:** NAV-007과 D-142는 카메라의 흰색 선 횡오차, 0.10 m/s 상한,
3초 소실 계약까지 정의했지만 실제 명령 소비, Pinky Pro의 3채널 IR 반사율
센서, 관제 모드 선택, 재현 가능한 시뮬레이션은 연결하지 않았다. 센서마다 별도
운전 모드와 최종 발행자를 만들면 D-2/D-38을 위반하고 전환 시 오래된 명령이
남을 수 있다.

**Decision:**

1. 차선 선택은 새 상위 운전 모드가 아니라 `NAVIGATION` 내부의 `OFF`,
   `IR_LINE`, `CAMERA_LINE` 배타적 하위 모드다.
2. Control은 원시 센서를 `source/visible/error/confidence/stamp` 관측으로만
   변환한다. CORE는 영상 바이트나 ADC 장치에 접근하지 않는다.
3. CORE `LineFollowManager`가 선택된 fresh 관측을 제한된 Navigation 후보
   속도로 변환하고, 기존 CommandManager/SafetyManager/ROS bridge가 유일한
   최종 `cmd_vel` 경로를 유지한다.
4. IR는 left/center/right별 검정·흰색 교정 끝점으로 정규화한다. 카메라는 하단
   ROI의 고전 CV 흰색 마스크를 사용한다. 임계값과 ROI는 제한된 설정값으로
   튜닝할 수 있지만 실제 장치 교정 전에는 DEVICE GO가 아니다.
5. stale, 미검출, 저신뢰 관측은 즉시 zero다. 3초 연속 소실 후
   `nav.lane_lost`를 한 번 발행하고 자동 탐색하지 않는다. 모드 전환, 일반 Nav2
   목표, E-stop은 차선 세션과 이전 관측을 폐기한다.
6. 관제는 CORE API로만 모드를 선택하고 상태·오차·신뢰도·명령·정지 사유를
   표시한다. 호스트 시뮬레이션은 실제 detector와 manager를 사용하되 물리
   반사율·조명·CSI·모터 검증을 대신하지 않는다.
7. 센싱 노드는 `rosy-io` 이미지와 hardware launch에 포함한다. 카메라는
   Picamera2 우선·V4L2/OpenCV fallback이며, IR는 기존 0x08 I²C ADC의 12-bit
   wire contract를 읽는다. 둘 다 명령을 발행하지 않는다. 영상 관측의 stale은
   수신 시각이 아니라 원본 `Image.header.stamp`부터 계산하고, API·ROS executor가
   공유하는 manager 상태는 하나의 재진입 잠금으로 직렬화한다.
8. V4L2 fallback도 settle 뒤 auto exposure와 auto white balance를 실제로 끄고
   readback이 manual임을 확인해야만 카메라 차선 evidence를 허용한다. IR endpoint와
   detector 임계값은 `/etc/rosy/line_follow.yaml` 외부 read-only mount로 주입해
   immutable 이미지를 다시 만들지 않고 로봇별로 교정한다. 제어 decision에는 mode
   generation을 넣어 계산과 CommandManager handoff 사이에 모드가 바뀐 경우 폐기한다.

**Alternatives:** 두 센서를 자동 융합하는 방식은 한 센서의 오교정이 다른 센서의
정상 관측을 덮을 수 있고 책임 소재가 흐려져 보류했다. 각 센서 노드가 직접
`cmd_vel`을 발행하는 방식은 단일 발행자 계약 위반으로 기각했다. Dashboard가
ROS 토픽을 직접 발행하는 방식도 외부 API 경계를 우회하므로 기각했다.

**Consequences:** 일반 Nav2와 차선 추종은 동시에 활성화되지 않는다. 카메라와 IR
프로필은 장치별 generation에 묶어야 하며, 내일 첫 장치에서는 흰색/검정 표본,
조명 변화, 좌우 부호, 정지 거리, 최대 속도를 별도로 검증해야 한다.

**Validation / Transition:** detector/manager/API/UI 계약 테스트, bridge 단일 발행자
구조 검사, IR·카메라 폐루프 운동학 시뮬레이션 JSON, hardware compose의
카메라·I²C device 전달 검사. 이후 Pinky Pro에서 교정값,
10 Hz 이상 관측, stale zero, 좌우 복귀, E-stop을 측정한다.

**References:** NAV-007, SAF-001, SAF-004, D-2, D-38, D-47, D-136, D-142.

---
