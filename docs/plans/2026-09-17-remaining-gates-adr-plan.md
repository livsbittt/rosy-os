# 남은 게이트 → ADR 계획

작성일: 2026-09-17
상태: D-78–D-81을 기록한다. G0–G3·카메라·OMX·IMU 융합은 기존 Proposed를 재사용한다.

관련: D-5, D-36, D-38, D-41–D-44, D-46, D-47, D-51–D-56, D-59, D-61, D-66, D-72, D-77 ·
[device-validation](2026-09-13-rosy-os-device-validation-implementation-plan.md) ·
[native Pi ARTIFACT](2026-09-17-arm64-artifact-native-pi-plan.md)

## 1. Goal

호스트에서 닫은 미들웨어(D-72, D-61, D-77) 뒤에 남은 일을 **이미 있는 ADR과
새 ADR로 가른다.** 새 ID는 비어 있던 경계만 채운다. D-41–D-56을 다시 쓰지 않는다.

이 계획이 ARTIFACT 이미지를 빌드하거나, Pi를 설치하거나, Fleet outbound를
구현하거나, IMU WIP를 커밋하거나, Pinky+OMX 합성을 켜지 않는다.

## 2. 남은 일 ↔ ADR

| 남은 일 | ADR | 이 계획이 하는 것 |
|---|---|---|
| ARTIFACT 빌드 경로 (QEMU HOLD) | **D-78** | 네이티브 Pi가 1순위임을 고정 |
| 계획 표의 옛 ROS-SIM GO vs 하네스 HOLD | **D-79** | 현재 트리 재실행만 GO |
| G4 HOST 조각 vs G4 GO | **D-80** | Device viewport가 GO 조건 |
| Fleet 콘솔 vs hub listen 없음 | **D-81** | v1 gather = CORE REST |
| G0 다섯 safety 상태·정지 거리 | D-51 Proposed | 재기록하지 않음 |
| G1 카메라 배치 | D-41, D-52 Proposed | 재기록하지 않음 |
| G2 Nav2/Control shadow | D-40 Accepted, D-44·D-52 Proposed | 재기록하지 않음 |
| G3 서명 readback | D-46, D-53 Accepted | Pi 인수만 남음 |
| 보정 schema·generation | D-43, D-47 | 재기록하지 않음 |
| OMX 작업 경계 | D-44, D-55 Proposed | 합성 Asset은 D-71 |
| IMU 융합 | D-56 Proposed | `src/rosy_imu_bno055/**` WIP 금지 유지 |
| 장치 패키지 SOURCE 얇음 | D-73 | host-contract 보강은 실행, 새 ADR 아님 |
| S8 (b) 콘솔 병합 | D-77 | DEVICE 전 금지 |
| apt/`rosyctl`·concept 09–12 | D-69, D-71 | v1 아님 |

## 3. 새 ADR 요약

전문은 [ADR 로그](../reference/ROSY%20ADR%20Log.md).

| ID | 결정 |
|---|---|
| D-78 | ARTIFACT 빌더는 네이티브 ARM64 Pi. 호스트 QEMU는 GO가 아니다 |
| D-79 | 모듈 gate GO는 progress가 가리키는 현재 트리 재실행만 |
| D-80 | G4 GO는 Device 표면. HOST 증거 4상태는 승격이 아니다 |
| D-81 | Fleet 콘솔 v1 gather는 CORE REST 폴링. outbound는 다음 단계 |

## 4. 실행 순서

### Task 1 — 기록 (이 커밋)

ADR 표·본문, 이 계획, device-validation §1 ROS-SIM 칸을 D-79에 맞게 HOLD로
정정, concept README 14·Fleet 행.

### Task 2 — 하지 않음

- native Pi 이미지 빌드 (D-78의 실행은 별도 계획)
- ROS-SIM 현재 트리 재실행 (D-79가 요구하는 증거, 이 Windows 호스트에 ROS 없음)
- G0 프로필 임계값, G4 viewport, 보정 상태기계
- `FleetAgent` outbound / `hub --listen`
- `src/rosy_imu_bno055/**` 커밋
- origin push

### Task 3 — 코드가 어기면 안 되는 방향

- 호스트 pytest를 ARTIFACT/DEVICE/G4 GO로 쓰지 않는다
- compose에 `web_node`를 넣지 않는다
- Fleet에서 `cmd_vel`을 내지 않는다
- CORE 이미지에 `rosy_control`/OpenCV/IMU를 넣지 않는다

## 5. 수락

- ADR 로그에 D-78–D-81 색인·본문이 있다.
- device-validation §1 ROS-SIM이 옛 GO를 주장하지 않는다.
- `python -m pytest test/test_network_topology_contracts.py test/test_harness_contracts.py -q`
