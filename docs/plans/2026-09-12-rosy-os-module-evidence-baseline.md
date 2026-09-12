# ROSY OS 모듈별 소스 근거 기준선

> 2026-09-13 편입 안내: 이 문서는 작성 당시의 조사·평가 근거다. 현재 제품 경계와 구현 순서는 [ADR D-37~D-44](../reference/ROSY%20ADR%20Log.md), [흡수 실행 계획](2026-09-12-rosy-control-absorption-plan.md), [최신 실행 결과](2026-09-12-control-absorption-results.md)를 우선한다. 조사 당시의 미실행·별도 Control 표기는 현재 배포 상태를 뜻하지 않는다.

작성일: 2026-09-12. 상태: 설계 평가용 소스 조사. 실물 인수 결과가 아니다.

## 조사 범위와 판독 규칙

- 현재 Rosy OS 체크아웃의 소스·설정·테스트 파일과 기존 조사 문서를 읽었다.
- 아래 M01–M14는 평가용 논리 식별자다. 패키지명, API 경로, 기존 요구사항 ID를 바꾸지 않는다.
- **소스 확인**은 구현 경로가 있다는 뜻이다. **테스트 존재**는 관련 테스트 파일이 있다는 뜻이며 충분한 커버리지나 성공을 뜻하지 않는다.
- 이 부록 작성 중 테스트·빌드·Pi 접속·장치 동작·배포를 실행하지 않았다. 모든 모듈의 이번 실행 증거는 **미실행**이다.
- 기존 문서의 완료·성능·설치 기록은 이번 장치 상태의 증거로 재사용하지 않는다.
- OMX 모델은 미선정이며 Pinky 직접 탑재, 가반하중, 전원, 바닥 도달은 계속 HOLD다.
- 관련 기존 범위: [하드웨어 조사](2026-09-12-mobile-manipulation-hardware-research.md), [영상·제어 조사](2026-09-12-mobile-manipulation-vision-control-research.md), [물리 검증 계획](2026-09-12-mobile-manipulation-validation-plan.md).

## 모듈별 기준선

| ID / 모듈 | 확인한 소스·설계 경로 | 관련 테스트 파일 존재 | 확장·유지보수 책임 |
|---|---|---|---|
| M01 호스트 OS·식별·전원 | [Compose](../../deploy/robot/compose.yaml), [identity](../../src/rosy_core/rosy_core/identity.py), [서비스 조립·배터리 설정](../../src/rosy_core/rosy_core/services.py) | [식별 계약](../../test/test_dds_identity_contracts.py), [배터리](../../src/rosy_core/test/test_battery.py) | 호스트는 부팅·권한 실행, CORE는 상태·정책을 담당. 암 전원·전압 강하·저전압 시 암 자세 정책은 추가 검증 필요 |
| M02 하드웨어 어댑터 | [모터 제어](../../src/rosy_bringup/rosy_bringup/motor_control.py), [Dynamixel 드라이버](../../src/rosy_bringup/rosy_bringup/dynamixel_driver.py) | [모터](../../test/test_motor_control.py), [드라이버 안전](../../test/test_dynamixel_driver_safety.py) | 현재 이동 베이스 경로를 OMX 관절 드라이버 완성으로 해석하지 않는다. 장치 식별·재연결·펌웨어 호환성은 장치별 책임 |
| M03 ROS 실행환경 | [CORE 노드](../../src/rosy_core/rosy_core/node.py), [ROS 브리지](../../src/rosy_core/rosy_core/bridge/ros_bridge.py), [Compose](../../deploy/robot/compose.yaml) | [Executor 계약](../../src/rosy_core/test/test_executor_contracts.py), [런타임 계약](../../test/test_robot_runtime.py) | CORE의 rclpy·웹 단일 프로세스 경계 유지. 시작 성공과 토픽 최신성·기능 준비를 분리 |
| M04 API·인증·기능 조회 | [권한 의존성](../../src/rosy_core/rosy_core/api/deps.py), [capability](../../src/rosy_core/rosy_core/capability.py), [스키마](../../src/rosy_core/rosy_core/protocol/schemas.py) | [API](../../src/rosy_core/test/test_api.py), [스키마](../../src/rosy_core/test/test_protocol_schemas.py) | 외부 진입은 CORE. viewer/operator/administrator 및 기능 광고를 새 암·비전 기능까지 계약 검토 후 확장 |
| M05 영상 전처리·인식·가속기 | [비전 프로세스 설계](2026-09-05-vision-accelerator-shield-design.md), [이번 영상 조사](2026-09-12-mobile-manipulation-vision-control-research.md) | 이 조사 범위에서 박스 인식 통합 테스트 확인 못함 | 별도 비전 실행 경계 제안. 카메라→전처리→인식의 시각·지연·큐·CPU/GPU/NPU 경로와 모델 버전 필요 |
| M06 보정·공간 상태 | [현재 상태 관리자](../../src/rosy_core/rosy_core/state/manager.py), [초기 위치](../../src/rosy_core/rosy_core/navigation/initial_pose.py), [보정 조사](2026-09-12-mobile-manipulation-vision-control-research.md) | [초기 위치](../../src/rosy_core/test/test_initial_pose.py) | 이동 위치 기반은 존재. 카메라–베이스–암 보정 버전, 물체·적재함 상태, 만료 판정 계약은 별도 필요 |
| M07 베이스 이동 | [navigation manager](../../src/rosy_core/rosy_core/navigation/manager.py), [목표 추적](../../src/rosy_core/rosy_core/bridge/goal_tracker.py) | [목표 추적](../../src/rosy_core/test/test_goal_tracker.py), [Nav2 하드웨어 구성](../../test/test_nav2_hardware_slice.py) | 목표 완료와 실제 정지 확인을 분리. 적재량·팔 수납 조건의 주행 제한은 추가 설계 |
| M08 암·그리퍼 | [OMX 후보·제어 조사](2026-09-12-mobile-manipulation-vision-control-research.md) | 이 조사 범위에서 OMX 제어 테스트 확인 못함 | src의 MoveIt/gripper/hand-eye 관련 Python·YAML·XML 검색에서 구현 경로 확인 못함. 제조사 연결·관절 제한·집기 결과 계약 필요 |
| M09 작업 실행 조율 | [기존 서비스 조립](../../src/rosy_core/rosy_core/services.py), [도킹 관리자](../../src/rosy_core/rosy_core/docking/manager.py) | [도킹](../../src/rosy_core/test/test_docking.py), [기존 운영 여정](../../src/rosy_core/test/test_operational_journey.py) | 도킹·주행 관리자를 범용 집기 작업 엔진으로 보지 않는다. 이동→정지→재인식→집기→수납의 기록·취소·재시작 정책 필요 |
| M10 배치·적층 계획 | [모바일 조작 연구](2026-09-12-mobile-manipulation-research.md), [검증 계획](2026-09-12-mobile-manipulation-validation-plan.md) | 이 조사 범위에서 박스 적층 테스트 확인 못함 | 공간 적합성 외 지지·무게중심·팔 접근·그리퍼 후퇴·하역 순서를 담당할 새 논리 경계 |
| M11 안전·명령 소유권 | [명령 관리자](../../src/rosy_core/rosy_core/command/manager.py), [중재](../../src/rosy_core/rosy_core/command/arbitration.py), [안전 관리자](../../src/rosy_core/rosy_core/safety/manager.py) | [CORE 로직](../../src/rosy_core/test/test_core_logic.py), [deadman](../../src/rosy_bringup/test/test_command_deadman.py) | 현재 속도 명령 중재를 암 안전 인증으로 보지 않는다. 베이스·암 공동 실행권과 통신 단절 시 장치별 정지·유지 정책 필요 |
| M12 웹 운영·정비 | [웹 진입](../../src/rosy_core/rosy_core/web/index.html), [웹 클라이언트](../../src/rosy_core/rosy_core/web/client.js), [설정](../../src/rosy_core/rosy_core/web/settings.js) | [대시보드](../../src/rosy_core/test/test_dashboard.py), [브라우저](../../test/test_dashboard_browser.py) | 현행 FastAPI 정적 웹 기반. 암 조작·보정·박스 배치·작업 중단 UX와 실제 권한 반영은 추가 검증 |
| M13 진단·증거 | [진단 수집](../../src/rosy_core/rosy_core/diagnostics/collector.py), [감사 기록](../../src/rosy_core/rosy_core/events/audit.py), [호스트 상태](../../src/rosy_core/rosy_core/system/runtime.py) | [진단 API](../../src/rosy_core/test/test_diagnostics_api.py), [감사](../../src/rosy_core/test/test_audit.py) | CPU·메모리 등 기존 진단에 영상 시각·보정·작업 단계·관절 오차·물체 확인 증거를 연결할 책임 |
| M14 릴리스·업데이트·복구 | [updater](../../deploy/release/updater.py), [저장공간 정책](../../deploy/release/storage.py), [릴리스 런타임 unit](../../deploy/robot/rosy-release-runtime.service) | [updater](../../test/test_release_updater.py), [스토리지](../../test/test_release_storage.py), [런타임](../../test/test_release_runtime.py) | 런타임 활성화·복구 기반 존재. 호스트 OS A/B 파티션, 암 보정·모델의 자동 호환 복구, 실물 전원 차단 복구가 입증된 것은 아님 |

## 확인한 중요한 유지보수 경계

### 업데이트와 기계 재가동

[updater.py](../../deploy/release/updater.py)는 journal 기록, activation.json 원자 교체, bounded CORE health 확인, 이전 release 복구 경로를 갖는다.
후보 활성화와 rollback 모두 core 모드로 돌아오는 구조다.
따라서 업데이트 성공은 모터·암의 자동 재활성화 승인이 아니다.
암 확장에서는 이전 작업을 자동 재개할지와 물체를 잡은 상태의 복구를 별도 계약으로 정해야 한다.
현재 원자 교체는 활성화 메타데이터 범위이며 전체 디스크·OS의 A/B 업데이트를 의미하지 않는다.

### 서비스 상태와 기능 상태

[rosy-runtime.service](../../deploy/robot/rosy-runtime.service)와 [릴리스 runtime service](../../deploy/robot/rosy-release-runtime.service)는 Type=oneshot, RemainAfterExit=yes다.
[Compose](../../deploy/robot/compose.yaml)의 restart: unless-stopped는 컨테이너 재시작 정책이다.
이 설정만으로 프로세스 교착 감지, 영상 최신성, 관절 제어 준비, 실제 안전 정지를 보장하지 않는다.
서비스 재시작 후에는 각 기능 준비와 실행권을 다시 평가해야 한다.

### ROS lifecycle 적용 범위

확인한 RosyCoreNode는 일반 Node 기반이다. 모든 로지 모듈이 lifecycle node라고 표기하면 안 된다.
ROS lifecycle의 configure/activate/deactivate/error 경계는 평가 설계에 참고하되, 일반 노드와 제조사 드라이버는 각 어댑터에서 준비·중지 결과를 관찰해야 한다.
평가표의 준비/고장/정비 상태는 ROS 표준 lifecycle enum이나 공개 API 필드를 새로 선언하는 것이 아니다.

## 공식 유지보수 근거

1. [ROS 2 Managed nodes 설계](https://design.ros2.org/articles/node_lifecycle.html): 구성·활성·비활성·오류 전환과 외부 관리자의 감독 개념. 실제 코드가 이 인터페이스를 구현했는지는 별도 확인 사항이다.
2. [systemd 공식 service 문서 원본](https://github.com/systemd/systemd/blob/main/man/systemd.service.xml): oneshot 상태와 RemainAfterExit, WatchdogSec·notify 및 Restart 정책을 구분한다. 위 로지 runtime unit에는 WatchdogSec 설정이 없다. upstream main 문서이므로 Pi에 설치된 systemd 버전별 지원은 실물 인벤토리에서 다시 확인한다.

## 다음 평가에 필요한 공통 증거

- 장치 모델·보드·펌웨어·배선·전원과 소스 SHA, 이미지 digest, 설정·보정·모델 버전.
- 테스트 존재 목록과 실제 실행 명령·시간·결과를 별도 기록.
- API 응답, 장치 보고, 카메라·관절·베이스 실측 결과를 분리.
- 실패·복구 시나리오에서 감지 시간, 제한 동작, 재가동 조건, 로그 위치.
- 변경 파일별 재검증 범위와 교체 부품·재보정 시 재인수 조건.


## 현재 코드 재검토 보완
이 문서의 조사 이후 Rosy Control과 OS 내부 Fleet까지 추적하고 선택 로컬 테스트 266개를 확인했다. 비전·주행의 기존 구현과 두 명령 경로를 반영한 [현재 구조·수정 계획](2026-09-12-rosy-os-system-architecture-roadmap.md)을 우선 참조한다. 기존 미실행 표시는 최초 조사 시점의 기록이며 실물 통합 인수는 여전히 미확인이다.
