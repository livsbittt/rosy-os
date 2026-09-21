## D-78 ARTIFACT 빌더는 네이티브 ARM64 Pi다

**Status:** Accepted (2026-09-17). 경로 결정이다. digest·서명·Pi 인수는 아직 HOLD.

**Context:** D-66 CORE 이미지(`rosy_control`/OpenCV 없음)의 ARTIFACT GO가 필요하다.
호스트 QEMU로 Hub `ros:jazzy-ros-base` linux/arm64를 빌드하면 CPython/colcon/
gcc가 0바이트인 hollow 레이어에서 죽었다. `ac81f2f` core/io digest는 D-66 이전이라
재사용할 수 없다. 그런데도 ARTIFACT를 호스트에서 닫으려는 시도가 반복된다.

**Decision:** ARTIFACT의 1순위 빌더는 **네이티브 linux/arm64 Pi**다.

- 호스트 QEMU 성공은 ARTIFACT GO가 아니다.
- Hub `jazzy-ros-base` arm64 현재 태그를 QEMU로 다시 돌리지 않는다.
- D-66 이전 digest는 재사용하지 않는다.
- 실행 순서는 [native Pi 계획](../plans/2026-09-17-arm64-artifact-native-pi-plan.md).

**Alternatives:** 건강한 과거 Hub digest를 QEMU에 핀하는 안은 우회일 뿐 1순위가
아니다. Windows 호스트 pytest로 ARTIFACT를 대체하는 안은 계층을 속인다.

**Consequences:** 이 호스트에서 ARM64 이미지가 없어도 미들웨어 ADR은 진행한다.
ARTIFACT/DEVICE는 deploy·rosy_core gate가 HOLD로 남는다. 이 결정이 이미지를
만들지 않는다.

**Validation / Transition:** `docs/deployment/arm64-build-notes.md`의 QEMU HOLD
기록. native Pi에서 `uname -m` = aarch64 뒤에 core 타깃 빌드. 호스트
`test/test_restore_hollow.py`는 restore 스크립트 가드이지 ARTIFACT GO가 아니다.

**References:** D-36, D-46, D-53, D-66,
[device-validation](../plans/2026-09-13-rosy-os-device-validation-implementation-plan.md),
[native Pi 계획](../plans/2026-09-17-arm64-artifact-native-pi-plan.md).

---
