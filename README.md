# ROSY — Robot Middleware & Fleet Control Platform

**Rosy** (ROS + Pinky 계보) — Pinky Pro 하드웨어(첫 구현)를 시작으로, 어떤 로봇이든
웹·표준 API로 제어하고 중앙 Fleet에서 군집 관리하는 범용 로봇 플랫폼.

> Upstream: [pinky_pro](https://github.com/pinklab-kr/pinky_pro) 기반 포크 — 전면 리네임(D-16), Apache-2.0.

## 구조

```text
rosy/ (이 리포지토리)
├── docs/                     # 문서 5종 (spec / reference / plan)
├── src/                      # ROS 2 패키지 (colcon workspace)
│   ├── rosy_core/            # 핵심 미들웨어 (API·Safety·Event·Waypoint·...)
│   ├── rosy_bringup/         # 모터·오도메트리·배터리
│   ├── rosy_navigation/      # Nav2/SLAM 설정·런치
│   ├── rosy_description/     # URDF
│   ├── rosy_gz_sim/          # Gazebo 시뮬레이션 (gz_multi.launch.py로 N대)
│   └── rosy_* (sensor/imu/led/emotion/lamp/interfaces)
└── .github/workflows/ci.yml  # colcon build + 테스트
```

## 문서 (거버넌스: docs/)

| 문서 | 역할 |
|---|---|
| `docs/spec/ROSY CORE SRS.md` | 로봇(엣지) 요구사항 |
| `docs/spec/ROSY FLEET SRS.md` | 중앙 서버 요구사항 |
| `docs/reference/ROSY API & Protocol Reference.md` | 공유 API/프로토콜 계약 |
| `docs/reference/ROSY ADR Log.md` | 의사결정 기록 (D-1~D-17) |
| `docs/plan/ROSY Implementation Plan.md` | 실행 계획·추적 매트릭스 |

## 빌드

```bash
cd src && colcon build --symlink-install
source install/setup.bash

# 시뮬레이션 2대 (멀티 인스턴스)
ros2 launch rosy_gz_sim gz_multi.launch.py robots:=2

# rosy_core (Phase 1 구현 예정)
ros2 launch rosy_core rosy_core.launch.py
```

## 로드맵

Phase 0 리네임·멀티로봇 리팩토링 → **Phase 1 rosy_core** → Phase 2 rosy_web →
Phase 3 2대 검증 → Phase 4 rosy_fleet → Phase 5 Formation → Phase 6 확장.
상세: `docs/plan/ROSY Implementation Plan.md`
