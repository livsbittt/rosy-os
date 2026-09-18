# 남은 실행 게이트 → ADR 계획

작성일: 2026-09-17
상태: D-87–D-99. D-54–D-56 소스 게이트 Accepted. D-41–D-44·D-51·D-52는 Device까지 Proposed (D-91). 축구 트랙은 D-90·D-94–D-99.

관련: D-35, D-59, D-78–D-81, D-83–D-86 ·
[남은 런타임](2026-09-17-remaining-runtime-adr-plan.md) ·
[native Pi ARTIFACT](2026-09-17-arm64-artifact-native-pi-plan.md)

## 1. Goal

호스트 카탈로그·Fleet REST 대기열 뒤에 남은 실행을 **순서 있는 ADR**로 고정한다.
D-83의 묶음, D-78의 빌더, D-81의 REST를 반복하지 않는다.

이 계획이 colcon을 돌리거나, Pi 이미지를 만들거나, `hub --listen`을 구현하거나,
origin을 푸시하지 않는다.

## 2. 남은 일 ↔ ADR

| 남은 일 | ADR | 다음에 할 실행 |
|---|---|---|
| WSL Jazzy만 있고 install 없음 | **D-87** | 그 트리 colcon install 뒤에 D-83 |
| x86 빌드를 ARTIFACT로? | D-78, D-87 | 아니요. 네이티브 Pi |
| hub --listen / FleetAgent | **D-88** | 사이트 PC, D-83 항목 3 다음 |
| D-35 대형을 로그로 열기 | **D-89** | Task 14 현재 트리 재실행 후 |
| G4 Device | D-80, D-51 | viewport |
| IMU / 도크 ESP32 / hardware COPY | D-56, D-84, D-85 | 기존 유지 |
| deploy identity SHA | D-86 | POSIX에서만 |
| Pinky 1v1 축구를 CORE 모드로? | **D-90** | 아니요. 노트북 게임 호스트 |
| games overhead가 D-41인가? | **D-94** | 아니요. 노트북 관측. D-41은 Proposed |

## 3. 새 ADR 요약

| ID | 결정 |
|---|---|
| D-87 | D-83은 `install/setup.bash`가 있는 Linux에서만. x86 빌드 ≠ ARTIFACT |
| D-88 | Fleet 소켓은 관제 PC. 로봇 이미지 금지. D-83 전 소켓 금지 |
| D-89 | D-35는 D-83 Task 14 재실행 전까지 닫지 않음 |
| D-90 | 축구는 게임 호스트. `RobotMode.SOCCER` 없음 |

## 4. 실행 순서 (다음 세션)

1. **기록 (이 커밋)**
2. Linux에서 현재 트리 colcon install (D-87) → D-83 네 묶음
3. 네이티브 Pi ARTIFACT (D-78)
4. DEVICE readback (D-46/D-53)
5. G0 다음 G4 (D-51, D-80)
6. D-83 항목 3 증거 뒤 D-35 후보, 그다음 D-88 소켓
7. **하지 않음** — Windows에서 ROS-SIM GO, x86 이미지를 ARTIFACT로, 로봇에 hub listen, 옛 maze 로그로 D-35 Accepted, origin을 증거로

## 5. 수락

- ADR 로그에 D-87–D-89 색인·본문이 있다.
- `python -m pytest test/test_network_topology_contracts.py test/test_harness_contracts.py -q`
