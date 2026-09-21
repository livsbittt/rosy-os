# Scene-Context Control Node ROS-SIM (2026-09-22)

판정: **PASS** — D-162 T3(road_observer_node scene context wiring)을 살아있는
ROS 그래프에서 검증했다. T3는 지금까지 호스트 소스 검사(test_road_observer_wiring)
와 순수 로직 시험만 거쳤고, 이 실행이 첫 노드 레벨 증거다.

## 방법

- WSL2 Ubuntu 24.04, ROS 2 Jazzy. 트리는 `git archive HEAD`(commit `89c1d11`)에
  control 패키지 재빌드(`/root/rosy-d162/src`).
- `ros2 run control road_observer_node --ros-args -p scene_context_enabled:=true
  -p scene_context_min_confidence:=0.4 -p require_camera_controls_stable:=false`
- 합성 카메라: `test_road_perception.py` 픽스처와 동일 기하의 numpy 프레임을
  10 Hz로 `/camera/front`에 3페이스 발행 — lane(3s) → lane+stop line(3s) →
  lane+crosswalk(5s). 신뢰도 문턱은 0.4(기본 0.5 대신 — 합성 crosswalk 신뢰도가
  0.5 근처로 낮기 때문).
- 검증 스크립트가 `/road/observation`을 구독해 payload를 JSONL로 수집하고
  전환 순서·리비전 결합을 단언한다.

## 결과

| 항목 | 결과 | 근거 |
|---|---|---|
| 수신 observation | 110건, 전부 `context` 필드 포함 | `road-observation-received.jsonl`, `verify-output.txt` |
| context 전환 | generic → lane_follow → stop_line → crosswalk 순서대로 출현(히스테리시스 진입 후) | `verify-output.txt` |
| 리비전 결합 | lane_follow=ctx-lane-v1, stop_line=ctx-stop-v1, crosswalk=ctx-crosswalk-v1 | `verify-output.txt` |
| sensing-only 유지 | 그래프 내 twist 토픽 **0개** — 노드는 motion을 발행하지 않는다 | `topic-list.txt`, `twist-count.txt` |
| 단일 evidence 발행자 | `/road/observation` Publisher count 1 | `roadobs-info.txt` |

VERDICT: PASS (7/7 checks). 프로파일 값은 v0 중립(제네릭과 동일)이므로 본
실행은 **메커니즘**의 그래프 증명이지 성능 이득의 증명이 아니다.

## 한계

- 검증 스크립트 자체가 판정 출력 후 teardown에서 SIGABRT로 종료된다
  (던진 스레드+shutdown 경합의 스크립트 결함). 제품 코드와 무관하고
  수집된 evidence는 판정 이전에 완성돼 있다.
- 실제 카메라 프레임, 조명·시간대 유지율, Gazebo 폐루프 주행은 여전히
  ROS-SIM(Gazebo)/DEVICE 게이트다.
- 이것은 control ROS-SIM HOLD 중 **D-162 슬라이스**만 닫는다. 나머지
  sensing/camera/calibration/planning/safety-policy 전체 그래프 재실행은
  별도로 남는다.
