# FastAPI 맵 스냅샷 (MAP-003) + Flask 런치 제거

**Date:** 2026-09-03
**Related:** D-3, MAP-003, P1-13, `docs/plan/ROSY Flask Parity Checklist.md` E-1

## Decision

Flask `GET /api/state`의 맵/path/costmap을 FastAPI 세 경로로 옮긴다.

- `GET /api/v1/map`
- `GET /api/v1/navigation/path`
- `GET /api/v1/map/costmap?scope=global|local`

`web_nav2` / `web_slam` / `gz_web_*` 런치는 Flask 노드 대신 `rosy_core`를 기동한다. `nav2_web_server.py` 파일은 이번 변경에서 삭제하지 않는다.

## Shape

ROS-free `MapSnapshotStore`가 마지막 OccupancyGrid / Path / Costmap dict를 보관한다. `ros_bridge`만 `map`, `plan`, `local_costmap/costmap(+_raw)`, `global_costmap/costmap(+_raw)`를 구독해 스토어를 채운다. REST는 스토어만 읽는다.

맵 토픽은 TRANSIENT_LOCAL QoS. 데이터 없으면 맵/코스트맵은 `404 NOT_FOUND`, path는 빈 목록 `200`. Viewer 토큰. 본문은 Flask 스냅샷과 같은 `{width,height,resolution,origin,data}` 이며 맵 응답에 `map_id`를 붙인다.

## Dashboard (MAP-004)

내장 대시보드 `field-map-panel`이 OccupancyGrid·global costmap·path·pose를 캔버스에 그린다. 클릭은 현재 yaw로 `POST /api/v1/navigation/goal`. 맵 없음은 404를 에러가 아니라 대기로 본다.

## Out of scope

OccupancyGrid 다운샘플, Flask `.py` 삭제, 실기 Nav2 E2E로 체크리스트 PASS 도장.
