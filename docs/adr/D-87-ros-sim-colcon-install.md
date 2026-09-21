## D-87 ROS-SIM은 그 트리의 colcon install이 있을 때만 시작한다

**Status:** Accepted (2026-09-17). D-83의 전제다.

**Context:** WSL에 `/opt/ros/jazzy`와 `rclpy`가 있다. 워크스페이스
`install/setup.bash`는 없다. 그 상태에서 `ros2 --help`나 호스트 pytest로
ROS-SIM을 닫으려는 시도가 있다. x86 WSL colcon은 편하지만 D-78 ARTIFACT
경로(네이티브 Pi)와 섞이기 쉽다.

**Decision:** D-83 묶음은 **그 커밋이 가리키는 트리에서 colcon으로 만든
`install/setup.bash`가 있는 Linux**에서만 시작한다.

- Jazzy가 깔려 있기만 한 WSL은 전제가 아니다
- Windows 호스트 pytest는 ROS-SIM이 아니다 (D-79)
- x86 워크스페이스 빌드가 성공해도 ARTIFACT GO가 아니다 (D-78)

**Alternatives:** `rclpy` import만으로 ROS-SIM GO는 계층을 속인다. 매번 소스
트리에서 `python`으로 노드를 띄우는 안은 install overlay와 다른 그래프가 된다.

**Consequences:** 지금 트리의 ROS-SIM은 HOLD. maze 로그는 역사이며 승격 증거가
아니다.

**Validation / Transition:** `test -f install/setup.bash` 뒤에 D-83 명령을
progress에 적는다. 그 전 GO는 이 ADR 위반이다.

**References:** D-78, D-79, D-83.

---
