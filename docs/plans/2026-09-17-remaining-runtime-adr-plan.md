# 남은 런타임 게이트 → ADR 계획

작성일: 2026-09-17
상태: D-83–D-86을 기록한다. G0–G3·카메라·OMX·IMU 융합은 기존 Proposed를 재사용한다.

관련: D-38, D-46, D-51–D-56, D-62, D-66, D-78–D-81 ·
[남은 게이트](2026-09-17-remaining-gates-adr-plan.md) ·
[native Pi ARTIFACT](2026-09-17-arm64-artifact-native-pi-plan.md) ·
[device-validation](2026-09-13-rosy-os-device-validation-implementation-plan.md)

## 1. Goal

호스트 SOURCE/LOCAL이 GO인 뒤에 남은 런타임 일을 **실행 순서 있는 ADR**로
고정한다. D-78–D-81(경로·증거 규칙)을 반복하지 않는다. D-41–D-56을 다시
쓰지 않는다.

이 계획이 Jazzy 컨테이너를 띄우거나, Pi 이미지를 빌드하거나, ESP32를
플래시하거나, IMU WIP를 커밋하지 않는다.

## 2. 남은 일 ↔ ADR

| 남은 일 | ADR | 다음에 할 실행 |
|---|---|---|
| ROS-SIM을 무엇으로 다시 도나 | **D-83** | Jazzy 컨테이너에서 네 묶음 |
| led/adc/lamp/emotion/IMU를 core 이미지에 넣을까 | **D-84** | 넣지 않음. hardware 프로필+Device |
| 도크 `.ino`로 ARTIFACT? | **D-85** | ESP32 툴체인 readback만 |
| Windows identity 13 fail | **D-86** | POSIX에서만 deploy SHA |
| ARTIFACT 빌더 | D-78 | 네이티브 Pi 계획 |
| G4 Device | D-80, D-51 | viewport 전 HOST로 GO 금지 |
| Fleet outbound | D-81, D-5 | D-83 Task 14 다음 |
| G1 카메라 | D-41, D-52 | Pi 실측 |
| IMU 융합 | D-56, D-84 | WIP 섞지 않음 |

## 3. 새 ADR 요약

| ID | 결정 |
|---|---|
| D-83 | ROS-SIM 최소 묶음: core 스모크, control 그래프, gz_multi 2대, Nav2 launch |
| D-84 | hardware 다섯 패키지는 hardware 프로필 전까지 CORE/io에 없음 |
| D-85 | 도크 ARTIFACT = ESP32 빌드·플래시 |
| D-86 | identity bash는 POSIX에서만 deploy last_verified |

## 4. 실행 순서 (사람이 다음 세션에서)

1. **기록 (이 커밋)** — ADR 표·본문, 이 계획.
2. **ROS-SIM (D-83)** — Linux/Jazzy. Windows에서 하지 않음.
3. **ARTIFACT (D-78)** — 네이티브 Pi core 이미지 digest.
4. **DEVICE (D-46/D-53)** — install + readback JSON.
5. **G0 다음 G4 (D-51, D-80)** — Device viewport.
6. **하지 않음** — IMU WIP 혼합, core에 hardware COPY, Windows에서 identity SHA, origin을 증거 계층으로 쓰기.

## 5. 수락

- ADR 로그에 D-83–D-86 색인·본문이 있다.
- `python -m pytest test/test_network_topology_contracts.py test/test_harness_contracts.py -q`
