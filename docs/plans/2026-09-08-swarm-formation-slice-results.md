# 군집 대형 슬라이스 — 시뮬 계측 결과

설계: `2026-09-08-swarm-formation-slice-design.md` §Testing Strategy.
환경: 미실행 — 아래 노트 참고.

2026-09-09: 이 세션은 Windows 개발 환경이라 ROS 2 Jazzy·Gazebo 가 없다. Task 1~13 의
코드와 호스트 테스트(`python -m pytest src/rosy_fleet/test -q`, 2026-09-09 기준 190개 이상 통과 — 정확한 수는 실행 시점의 것을 쓴다)는 끝났고, Task 12 Step 5 의 선행 관문
(`gz_multi robots:=2 mode:=nav core:=true` 런타임 확인)과 Task 14 의 네 시나리오는
**실행되지 않았다**. 아래 표의 빈 칸은 측정 전이라 비어 있다 — 측정하지 못한 것을
깨끗한 결과로 적지 않는다
(`docs/solutions/workflow-issues/inability-to-check-recorded-as-clean-result.md`).

| 항목 | 기준 | 실측 | 판정 | 출처 |
|---|---|---|---|---|
| 스트림 | 팔로워별 `relay_tx_hz ≥ 10` | | 미실행 | follow.csv |
| 추종 | 정상 주행 `slot_err_m` 중앙값 (기준값은 이 값이 정한다), holding 없음 | | 미실행 | follow.csv |
| 재배정 | LINE → V 뒤 새 슬롯 수렴, 교차 없음 | | 미실행 | reform.csv |
| HOLD | pause 뒤 전원 holding ≤ 1 s + 폴링 간격 1 s | | 미실행 | hold.csv, 콘솔 |
| FOR-004 | stuck 뒤 전원 정지, 리더 nav.canceled | | 미실행 | stuck.csv, 콘솔 |

## 선행 관문 (Task 12 Step 5) 에서 발견한 것

아직 실행되지 않았다.

## 관찰

아직 실행되지 않았다.

## D-35 등록 여부

아직 실행되지 않았다. HOLD ≤ 1 s 가 실측으로 보이기 전까지 D-35 는 후보로 남는다.

## 다음 슬라이스

- 실물 2대 FAT-06 변형(릴레이 pause 주입).
- `deploy/robot/config/capabilities.hardware.yaml` 의 `swarm.follow/lead` 점등 — 이 슬라이스에서는 켜지 않는다.
