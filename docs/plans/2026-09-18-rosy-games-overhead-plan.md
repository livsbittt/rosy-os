# rosy_games 천장 카메라 실측 계획

작성일: 2026-09-18
상태: 합성 어댑터는 트리에 있다 (D-94, D-95). 실제 웹캠 실측은 D-96 계단 1. Device GO가 아니다.

관련: D-90, D-91 · [game host 설계](2026-09-17-robot-soccer-game-host-design.md) · [LOCAL 호스트](2026-09-18-rosy-games-local-host.md)

## Goal

`host/overhead.py`와 `field/homography.py`만 추가한다. OpenCV는 그 두 파일에만
산다. LOCAL pytest는 이 파일을 **import하지 않고** 통과해야 한다. 기본
`exec_depend`에 OpenCV를 넣지 않는다.

만들지 않는 것: CORE 변경, `RobotMode.SOCCER`, Isaac, D-41 카메라 위치 승격,
현장 충돌 속도 GO.

## 수락

- 모서리 마커 → 필드 m. 공·로봇 pose가 `Observation`이 된다
- `MatchHost.arm()` 뒤 `tick()`이 가짜 관측 대신 overhead 소스를 받을 수 있다
- DEVICE/FIELD는 노트북 1v1 실측 전까지 PARKED

실행은 웹캠이 있는 자리에서. 이 Windows 호스트 pytest로 닫지 않는다.
