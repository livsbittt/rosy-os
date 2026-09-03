# Pinky Pro — ROSY OS v1 첫 보드 지원

Pinky Pro는 ROSY OS의 첫 하드웨어다. 이 문서는 그 보드 지원 범위다. 새 리눅스가
아니라 Raspberry Pi OS Lite 64-bit + Device Runtime + CORE + 어댑터다.

설계: `docs/plans/2026-09-01-rosy-os-v1-image-release-design.md`.

## 런타임 모드가 광고하는 기능

`ROSY_RUNTIME_MODE`가 CORE에 마운트되는 capability/profile을 고른다.
광고와 실장이 같아야 한다.

| 모드 | 서비스 | 장치 | Capability |
|------|--------|------|------------|
| `core` (기본) | `rosy-core` | 없음 | teleop/lidar/nav/slam 꺼짐 |
| `motor` | + `rosy-motor` | UART4 Dynamixel만 | teleop + encoder. lidar/nav 꺼짐 |
| `hardware` | + `rosy-io` | 모터 + RPLidar (`/dev/ttyAMA0`) | teleop + encoder + lidar. **nav/slam 꺼짐** |

Nav2와 SLAM은 아직 이미지에 없다. 대시보드 맵 클릭은 `goal_navigation: false`라
501이다. IMU·ADC·LCD·LED·lamp는 io 이미지에 넣지 않았다.

`GET /api/v1/host/commissioning`은 모드를 CORE가 직접 보고한다.
`motor_hold`는 `core`에서만 참, `lidar_hold`는 `hardware`가 아니면 참이다.

## 시운전 순서

1. 이미지는 항상 `core`로 기동한다. `MOTOR_HOLD`는 유지한다.
2. UART4와 토크 없는 ping이 끝나면 `.env`에서 `ROSY_RUNTIME_MODE=motor`.
3. LiDAR 수락 후 `hardware`. 모터와 hardware 프로파일은 동시에 켜지 않는다.
4. 서명 SD 이미지는 아직 없다 (`BUILD_GO` HOLD). 개발 태그는 현장이 아니다.

파일: `deploy/robot/config/capabilities.{core,motor,hardware}.yaml`.
`capabilities.pi5-lite.yaml`은 hardware 별칭이다.
