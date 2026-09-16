# 모듈형 미들웨어 목표

작성일: 2026-09-16

상태: D-63 Accepted(목표). 자식 ADR이 한 이음새씩 닫는다. D-62·D-64·D-66은 소스 완료. 매핑 분리·nav overlay는 남는다.

관련: D-1, D-22, D-38, D-57, D-59, D-60, D-62, D-64 · [선택 슬라이스](2026-09-16-optional-runtime-slices-design.md)

## 목표

Pi 5와 OMX/AI가 **같은 CORE**를 쓴다. CORE는 필수이고 얇다. 모터·LiDAR·Nav2·카메라·팔·추론은 각자 슬라이스다. 각 슬라이스는 ROS 메시지 가족 하나와 프로세스(또는 기존 compose 서비스)를 소유한다. CORE는 슬라이스 패키지를 import하지 않고, 최종 `cmd_vel`만 낸다.

설치는 슬라이스를 고른다. 없는 슬라이스는 이미지에 없고 capability는 false다.

## 끝 상태 가드

1. `rosy-core` 이미지에 MoveIt, NPU SDK, Picamera, `rosy_omx_adapter`가 없다.
2. `rosy_core` 생산 코드가 `rosy_control`을 import하는 곳은 센서 어댑터 한 파일뿐이다. 그다음 단계에서 그 파일도 토픽 경계로 바뀐다.
3. `safety/`, `command/`, `navigation/`은 벤더·카메라·팔을 모른다.
4. compose 기본은 `{rosy-core, rosy-motor, rosy-io}`. nav/vision/omx/ai는 overlay.
5. 꺼진 슬라이스가 없어도 CORE는 기동한다. 주행이 필요하면 readiness HOLD.

## 순서 (자식 ADR)

| 단계 | ADR | 닫는 이음새 | 상태 |
|---|---|---|---|
| 1 | D-62 | 설치 카탈로그, preset, first-boot는 core | 이 브랜치에서 소스 완료 |
| 2 | D-64 | CORE 생산 코드의 `rosy_control` import를 어댑터로만 | 소스 완료 |
| 3 | D-66 | CORE 이미지에서 OpenCV/`rosy_control` COPY 축출 | 소스 완료 |
| 4 | 후속 | 매핑 세션을 navigation에서 분리 (기존 C7) | 아직 아님 |
| 5 | 후속 | nav compose overlay (hardware 묶음 해제) | 아직 아님 |
| 6 | 후속 | vision/omx 설치 가능 overlay (D-52, D-55 실측 후) | 아직 아님 |

한 단계에서 CORE 프로세스를 쪼개거나 로봇에 브로커를 올리지 않는다.
