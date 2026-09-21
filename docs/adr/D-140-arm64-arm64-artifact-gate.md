## D-140 ARM64 소스 검증은 공개 arm64 러너로 매주 리허설한다 — ARTIFACT gate 의 코드 수준 선검증

**Status:** Accepted (2026-09-20).

**Context:** ARTIFACT gate 가 HOLD 인 이유 중 하나는 "ARM64 개발 후보만 존재" — 네이티브 arm64 에서의 코드 검증이 Pi 없이는 불가능했다(D-66/D-78 은 이미지 빌드 단계). 이 저장소는 public 이므로 GitHub 의 arm64 호스티드 러너(ubuntu-24.04-arm)가 무료이고, ROS 2 Jazzy apt 패키지는 arm64 를 지원한다.

**Decision:**

1. **매주 목요일 + 수동 트리거로 arm64 리허설을 실행한다.** ubuntu-24.04-arm 에서 ROS Jazzy base 설치 → `colcon build src` → core ROS-free 스위트. 비게이팅(continue-on-error) — 실패는 ARTIFACT 진입 전에 발견하는 것이 목적이다.
2. **이미지 빌드 자체는 D-66 대로 네이티브 Pi 에서 한다.** 이 리허설은 코드 수준 선검증이며 deploy/image 파이프라인을 대체하지 않는다.
3. **리허설 적색은 ARTIFACT 준비의 할 일 목록이다.** 녹색이 연속되어도 ARTIFACT gate 승격은 D-78 절차를 따른다.

**Alternatives:** QEMU 에뮬레이션 — 느리고 D-66 이 금지한다. Pi 상시 연결 — 하드웨어 비용과 대기 시간. 무시 — 이주 후 적색 발견은 늦다.

**Consequences:** 주간 arm64 CI 실행(공개 저장소 무료). ROS Jazzy arm64 apt 의존(apt.ros.org arm64 지원). 리허설 적색이 ARTIFACT 준비의 가시적 신호가 된다.

**Validation / Transition:** 최초 실행에서 빌드·스위트 통과를 확인한다. 연속 녹색이면 ARTIFACT gate 진입 시 "코드 수준 네이티브 검증" 증거로 인용한다.

**References:** D-66, D-78, actions/runner-images(Ubuntu 26.04/24.04 arm64), changelog 2026-09-17.

---
