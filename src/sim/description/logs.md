# description logs

추가만 한다. 형식: [module harness 설계](../../docs/plans/2026-09-15-module-harness-design.md) §4.2.
2026-09-15 이전 이력은 `git log -- src/description`를 본다.

## 2026-09-15 · uncommitted · docs(harness): start the description harness record
- 변경: `progress.md`, `logs.md` 추가
- 증거: `python3 -m pytest test/test_robot_runtime.py::test_runtime_builds_distinct_targets_from_shared_dockerfile -q` 1 passed; LOCAL은 미실행 — `src/description`에 `test/` 디렉터리가 없어 host-runnable 대상이 없음 (2026-09-15 Windows)
- gate 변화: 없음(신규 기록). SOURCE GO, LOCAL HOLD, ROS-SIM N/A, ARTIFACT/DEVICE HOLD(io 이미지에 포함, Device 계획과 동일 blocker), FIELD N/A
- 결정: D-61 Proposed
- 교훈: 없음

## 2026-09-16 · uncommitted · docs(harness): hold unrendered description in ROS-SIM
- 변경: 리뷰 반영. ROS-SIM을 HOLD로, `last_verified.commit`을 `uncommitted`로(SOURCE 시험이 미커밋 WIP가 있는 `deploy/robot/Dockerfile`을 읽음)
- 증거: `python -m pytest test/test_robot_runtime.py::test_runtime_builds_distinct_targets_from_shared_dockerfile -q` 1 passed (2026-09-16 재실행). ROS 렌더 자체는 미실행
- gate 변화: ROS-SIM N/A→HOLD (URDF는 robot_state_publisher·Gazebo가 소비하므로 적용 대상이지만 미검증)
- 결정: 없음
- 교훈: 없음

## 2026-09-16 · uncommitted · docs(harness): stop counting the meshes dockerignore check as source evidence
- 변경: 2차 리뷰 반영. SOURCE를 HOLD로(인용 시험은 `.dockerignore` meshes 제외만 확인하고 URDF·io-build 포함을 단언하지 않음), FIELD를 PARKED로(io 이미지에 실리는 패키지)
- 증거: 미실행 — 기록 정정만. 인용 시험 내용은 `test/test_robot_runtime.py`에서 직접 확인
- gate 변화: SOURCE GO→HOLD, FIELD N/A→PARKED
- 결정: 없음
- 교훈: 없음
