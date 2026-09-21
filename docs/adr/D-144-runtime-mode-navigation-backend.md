## D-144 하드웨어 맵 생성은 runtime mode가 아니라 검증된 navigation backend다

**Status:** Accepted (2026-09-21). 설계와 실행 계획:
`docs/plans/2026-09-21-hardware-mapping-g5-design.md`,
`docs/plans/2026-09-21-hardware-mapping-g5.md`.

**Context:** Pinky Pro G5 절차는 SLAM 시작·저장 API를 호출하지만 현재 `hardware`
그래프는 AMCL과 map server 기반 현지화만 실행한다. capability는 `slam: false`, IO
이미지에는 SLAM Toolbox가 없고 지도 mount도 read-only다. 따라서 문서대로는 실제
지도를 생성할 수 없으며, API 응답만으로는 원시 센서 자료와 실제 지도 파일을
증명하지 못한다.

**Decision:** `ROSY_RUNTIME_MODE=hardware`는 장치 slice 정체성으로 유지하고,
`ROSY_NAVIGATION_BACKEND=localization|slam`을 직교 선택으로 둔다. 기본
`localization`은 기존 AMCL/map-server 그래프와 read-only 지도 mount를 유지한다.
`slam`은 Nav2+SLAM Toolbox 그래프, `slam: true` 전용 capability, SLAM lifecycle
readiness, 지도/커미셔닝 디렉터리의 제한된 쓰기 mount만 활성화한다. `slam` backend는
`hardware` 외 mode에서 시작 전에 거부한다. 지도 이름은 안전한 basename으로 제한해
`/var/lib/rosy/maps` 아래에 저장하고, G5는 scan·odom·cmd_vel·map·TF의 bounded MCAP과
실제 YAML/PGM 쌍을 해시해 보존한다.

**Alternatives:** 별도 `mapping` runtime mode는 core/motor/hardware 장치 slice 계약을
불필요하게 복제하므로 기각한다. 현지화와 SLAM을 동시에 상시 실행하는 방식은 TF
소유권 충돌과 capability 오광고 때문에 기각한다. 일반 hardware capability를 항상
`slam: true`로 두는 방식도 서비스가 없는 상태에서 API를 광고하므로 기각한다.

**Consequences:** backend 전환에는 runtime restart가 필요하다. 일반 주행의 지도
디렉터리는 계속 read-only다. host/Docker 검증은 구현 증거일 뿐이며 DEVICE/FIELD GO는
실제 Pinky에서 MCAP, 지도 산출물, 무충돌 goal, 최종 E-stop과 zero velocity를 모두
확보한 뒤에만 가능하다.

**References:** D-2, D-4, D-13, D-22, D-33, D-47, D-54, D-66, D-137,
`pinky-pro-first-device-runbook.md`.

---
