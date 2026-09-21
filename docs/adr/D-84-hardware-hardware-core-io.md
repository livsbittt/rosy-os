## D-84 hardware 장치 패키지는 hardware 프로필 전까지 CORE/io에 없다

**Status:** Accepted (2026-09-17). D-62 슬라이스 규칙의 장치 쪽이다.

**Context:** led / adc / lamp / emotion / `rosy_imu_bno055`는 패키지와 HOST
계약 시험이 있다. `deploy/robot/Dockerfile` core/io는 이들을 복사하지 않는다.
그런데도 이미지에 슬며시 넣으려는 수정이 반복된다. IMU 소스는 다른 커밋과
섞지 않기로 한 WIP다.

**Decision:** 이 다섯 패키지는 **hardware 프로필이 Device 증거로 열리기 전**에
`rosy-core` / `rosy-io` 이미지에 넣지 않는다.

- `test_io_image_packages_nav2_without_slam_or_aux_drivers`가 제외를 지킨다
- IMU 융합은 D-56 Proposed. `src/rosy_imu_bno055/**` 구현 WIP는 다른 주제
  커밋과 섞지 않는다
- HOST 계약 시험 GO는 이미지 편입이 아니다

**Alternatives:** 전부 io에 넣는 안은 Pi 이미지에 드라이버와 OpenCV를 다시
싣는다(D-66과 충돌). 패키지를 지우는 안은 Device 프로필을 막는다.

**Consequences:** ARTIFACT 기본 이미지는 CORE+io(+nav overlay)다. hardware
슬라이스는 G1/G0 증거가 있을 때 연다.

**Validation / Transition:** `test/test_nav2_hardware_slice.py` io 제외 단언.
Dockerfile core/io에 다섯 패키지 COPY가 생기면 이 ADR 위반이다.

**References:** D-56, D-57, D-62, D-66,
[optional slices](../plans/2026-09-16-optional-runtime-slices-design.md).

---
