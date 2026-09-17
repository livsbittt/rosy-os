# rosy_bringup logs

추가만 한다. 형식: [module harness 설계](../../docs/plans/2026-09-15-module-harness-design.md) §4.2.
2026-09-15 이전 이력은 [Device 검증 계획](../../docs/plans/2026-09-13-rosy-os-device-validation-implementation-plan.md)과 `git log -- src/rosy_bringup`를 본다.

## 2026-09-15 · uncommitted · docs(harness): start the rosy_bringup harness record
- 변경: `progress.md`, `logs.md` 추가
- 증거: `python -m pytest test/test_motor_control.py test/test_bringup_motor_contracts.py test/test_dynamixel_driver_safety.py src/rosy_bringup/test/test_command_deadman.py src/rosy_bringup/test/test_pinky_pro_adapter.py -q` 77 passed (2026-09-15 Windows, 미커밋 WIP 포함 작업 트리); `python -m pytest test/test_bringup_motor_contracts.py -q` 5 passed
- gate 변화: 없음. SOURCE/LOCAL GO, ROS-SIM/ARTIFACT/DEVICE HOLD, FIELD PARKED를 처음 기록
- 결정: D-61 Proposed
- 교훈: 없음

## 2026-09-16 · uncommitted · docs(harness): record the bringup source rerun count
- 변경: 위 항목의 `test_bringup_motor_contracts.py` 5 passed는 오기다. `progress.md` SOURCE 증거와 `cmd`(`python3`)를 정정
- 증거: `python3 -m pytest test/test_bringup_motor_contracts.py -q` 9 passed; LOCAL 5개 파일 77 passed (2026-09-16 재실행)
- gate 변화: 없음
- 결정: 없음
- 교훈: 없음
