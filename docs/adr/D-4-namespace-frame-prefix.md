## D-4 Namespace + frame_prefix 조합

**Status:** Accepted (2026-08)

**Context:** 멀티로봇에서 ROS 토픽·TF 충돌을 방지해야 한다. 기존 `gz_bringup_launch.xml`이 namespace + `/tf→tf` 리매핑 패턴을 이미 검증했다.

**Decision:** namespace + frame_prefix 조합을 표준으로 한다(예: `/rosy_01/cmd_vel`, TF `rosy_01/odom`).

**Consequences:** 검증된 패턴 재사용으로 리스크 최소. 절대경로 토픽(`/scan` 등)은 제거 대상(Impl Plan P0-2).

---
