# 선택 설치 런타임 슬라이스 설계

작성일: 2026-09-16

상태: 카탈로그와 installer가 기존 `core|motor|hardware` 모드에 연결됨. vision/omx/ai는 아직 기동하지 않는다. OMX·AI·카메라 실기 인수는 이 문서가 GO로 만들지 않는다.

관련: D-1, D-22, D-33, D-38, D-48, D-55, D-57, D-58, D-59, D-60 · [runtime maintainability](2026-09-03-runtime-maintainability-rules.md) · [사이트 패브릭](2026-09-14-site-middleware-role-fabric-design.md) · [Device 검증](2026-09-13-rosy-os-device-validation-implementation-plan.md)

## 1. 방향

ROSY는 로봇 안의 얇은 미들웨어다. **CORE만 필수**다. 모터, LiDAR, Nav2, 카메라, OMX, AI는 같은 ROS 그래프(localhost, D-33)에 붙는 **선택 슬라이스**다. Pi 5 한 대에 전부 넣을 필요가 없고, OMX-AI 보드에도 CORE 계약은 같다.

CORE를 여러 프로세스로 쪼개지 않는다(D-1). 어댑터가 최종 `cmd_vel`을 내지 않는다(D-38). 사이트 브로커를 로봇에 올리지 않는다(D-59).

지금 런타임은 `core` / `motor` / `hardware` 세 모드다. 카탈로그가 모드 이름에 센서·Nav2를 묶어 두어서, 카메라·팔·AI를 넣으려면 hardware를 부풀리거나  squatting하게 된다. 그걸 슬라이스 목록으로 바꾼다.

## 2. 세 가지 길

**1. CORE를 메시지 도메인마다 노드로 분해 (비추천)**  
명령·안전·대시보드를 패키지로 쪼개 각각 launch. D-1과 단일 `cmd_vel` 소유가 깨진다.

**2. 이미지 하나에 전부 넣고 capability만 끄기 (비추천)**  
설치는 쉽지만 Pi 이미지가 OMX·OpenCV·NPU를 항상 싣는다. 지금 `core` 스테이지가 `python3-opencv`와 `rosy_control`을 이미 넣는 빚을 키운다.

**3. 슬라이스 카탈로그 + 선택 설치 (추천)**  
필수 슬라이스 `core`. 나머지는 compose 서비스 또는 기존 profile에 매핑되는 설치 단위. 각 슬라이스는 ROS 토픽 가족 하나와 프로세스 하나(또는 기존 io/hardware 서비스)를 소유한다. CORE는 슬라이스 코드를 import하지 않고 토픽·capability만 본다.

## 3. 슬라이스와 메시지 책임

| 슬라이스 | 기본 | 산다 | ROS에서 하는 일 | 하지 않는 일 |
|---|---|---|---|---|
| **core** | 필수 | `rosy-core` 이미지, `rosy_core` | API, 안전, 최종 `cmd_vel`, EventBus, 대시보드 | `/dev`, 원본 영상, MoveIt, NPU |
| **motor** | 선택 | `rosy-motor` / bringup 모터 | `cmd_vel` 구독, odom, `motor/ready`, deadman | FastAPI, Nav2 |
| **io** | 선택 | `rosy-io` | 열거된 센서(LiDAR 등) | CORE 장치 개방 |
| **nav** | 선택 | hardware 런치의 Nav2 | 맵, AMCL, controller, `nav_cmd_vel` 후보 | 최종 mux, 사이트 버스 |
| **vision** | 선택, 기본 꺼짐 | 이후 vision 컨테이너 (D-41/D-52) | `camera/telemetry` 등 compact evidence | `cmd_vel`, 안전 허가 |
| **omx** | 선택, 기본 꺼짐 | `rosy_omx_adapter` + 이후 arm 런치 | 관절 상태, FollowJointTrajectory | 베이스 `cmd_vel`, CORE 안전 우회 |
| **ai** | 선택, 기본 꺼짐 | 이후 추론 슬라이스 | 검출 요약 토픽 | 원본 프레임 상시 송출, 모션 허가 |
| **fleet-relay** | 관제 PC | `rosy_fleet` | 계약 gather/scatter | 로봇 ROS, `cmd_vel` |

의존: 슬라이스 → CORE 토픽. CORE → 슬라이스 패키지 import 금지. 꺼진 슬라이스의 capability는 false이고, 관련 토픽이 없어도 CORE는 기동한다. 주행이 필요하면 readiness 게이트가 HOLD다(D-58).

## 4. 설치

`board.yaml`이 모드 하나가 아니라 **슬라이스 집합**을 고른다.

```yaml
board: pinky_pro
host: raspberry-pi-5
slices:
  required: [core]
  available: [motor, io, nav, vision, omx, ai]
presets:
  core: [core]
  motor: [core, motor]
  hardware: [core, motor, io, nav]
```

`install-pi.sh --preset hardware` 또는 `--slices core,motor,io`. 없는 슬라이스는 이미지·유닛·capability를 설치하지 않는다. OMX-AI 호스트는 `--slices core,omx`처럼 CORE+팔만 고른다.

이미지 규칙:

- `core` 타깃에 MoveIt, NPU SDK, Picamera를 추가하지 않는다.
- 선택 슬라이스는 자기 이미지 또는 io/hardware 스테이지에만 산다.
- 이미 CORE에 들어 있는 `rosy_control`/OpenCV는 부채다. 새 슬라이스를 넣지 않고, vision이 분리되면 CORE에서 빼는 후속이다.

검증:

- `capabilities.core.yaml`에 `omx` / `vision` / `ai` / `swarm.follow`가 켜져 있지 않다.
- compose 기본 서비스 집합은 `{rosy-core, rosy-motor, rosy-io}`를 넘지 않는다. vision/omx 서비스는 profile 또는 별도 compose overlay로만 생긴다.
- CORE 패키지 소스가 `rosy_omx_adapter` / 미래 vision 패키지를 import하지 않는다.

## 5. 하지 않는 것

- CORE 프로세스 분해, 로봇 Kafka/NATS, 로봇 간 DDS.
- 지금 compose에 `rosy-omx` / `rosy-vision` 데몬을 켜서 하드웨어를 여는 것.
- Device ARTIFACT/Pi GO를 이 카탈로그만으로 승격.
- `rosy_core` Python 서브패키지를 메시지마다 쪼개기 (그건 module-split 기준, 설치 단위가 아님).

## 6. 전환

1. 카탈로그와 시험으로 슬라이스 이름을 고정한다. 동작은 현재 `core|motor|hardware` preset과 같다.
2. `install-pi.sh`가 preset/slices를 받고, 설치하지 않은 슬라이스의 유닛을 만들지 않는다.
3. vision/omx/ai는 capability false + 빈 overlay로만 예약한다. 실기 배치는 D-52, D-55를 따른다.
4. ARM64 이미지는 슬라이스마다 digest를 가질 수 있게 Device 계획을 확장한다. 지금 게이트를 건너뛰지 않는다.
