# Rosy Control → Rosy OS 흡수 실행 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 기존 Rosy Control 기능을 Rosy OS 내부 패키지·API·명령·배포·정비 체계로 흡수하여 OS 단독 설치로 운영한다.
**Architecture:** Rosy OS/src/rosy_control로 먼저 편입하여 기존 import와 테스트를 보존한다. 최종 외부 API·웹·명령 중재는 rosy_core, 하드웨어 실행은 OS 내부 노드와 bringup, 배포·복구는 기존 deploy가 소유한다.
**Tech Stack:** 현재 ROS 2 Jazzy, ament_python/colcon, FastAPI+rclpy, OpenCV/NumPy, Docker/systemd 기반. 카메라 Picamera2/libcamera의 실제 ARM64 실행 위치는 배포 검증에서 결정한다.

작성일: 2026-09-12. 상태: 계획만 작성. 코드 복사·수정·이동·커밋·장치 배포 미실행. 작업 순서는 아래 의존성을 따른다. 테스트 명령은 향후 실행용이며 통과 기록이 아니다.

## 1. 범위와 설계 결정

사용자가 확정한 제품은 Rosy OS다. 별도 Control 제품·서버·설치를 최종 구성으로 유지하지 않는다. 내부 Python 패키지명 rosy_control을 유지하는 것은 코드 호환 선택이며 별도 제품 유지가 아니다.

[전체 구조](2026-09-12-rosy-os-system-architecture-roadmap.md)의 perception/autonomy/calibration 신규 패키지는 이전 목적을 설명한 후보였다. 실제 내부 참조를 확인했으므로 **이번에는 하나의 OS 내부 rosy_control 패키지로 편입**한다. 의미 없는 대량 import 변경과 기능 이전을 동시에 하지 않는다. 이후 분리는 실제 소유권·의존성 문제가 있을 때 별도 판단한다.

현재 확인 규모는 Python 소스 109개, test_*.py 108개, launch Python 10개다. 파일 개수이며 테스트 케이스 수가 아니다. source/setup.py는 11개 실행 entrypoint를 선언한다. 이 목록은 구현 시작 때 다시 고정한다.

이번 범위:
- 기존 감지·카메라·보정·계획·주행·안전·진단·웹 기능 및 테스트 흡수.
- CORE의 단일 외부 진입·명령권·설정·배포·복구로 통합.
- 기존 운용 기능의 동등성 확인.

후속 범위: OMX·박스 인식·hand-eye·적층·모바일 암. 흡수 단계에 신규 업무 알고리즘을 섞지 않는다. 원본 저장소 삭제와 Fleet 구조 변경도 이번 완료 조건에 포함하지 않는다.

## 2. 경로 기준과 이전 대장

S = 현재 Rogic/Rosy Control, D = Rosy OS. 아래는 상대 경로다. D/src/rosy_control 및 명시한 신규 테스트·문서는 **계획상 생성 대상**이다.

| 원본 | 목적지 | 방식·검증 |
|---|---|---|
| S/rosy_control/** | D/src/rosy_control/rosy_control/** | 처음에는 보존 복사. 이후 경계 변경만 작은 단위로 적용 |
| S/test/** | D/src/rosy_control/test/** | 테스트·fixture 함께 편입; 원본 경로 없이 수집/실행 |
| S/package.xml, setup.py, setup.cfg, resource/rosy_control | D/src/rosy_control의 동일 상대 위치 | 의존성·entrypoint·ament 리소스 검증 |
| S/config/*.yaml | D/src/rosy_control/config/*.yaml | 기본값과 장치 실측값 분리. 실측 보정값을 범용 이미지 기본값으로 배포하지 않음 |
| S/launch/*.py | D/src/rosy_control/launch/*.py | 초기 비교 자료로 보존, OS용 launch에서 필수 노드만 선택 |
| S/web/**, web_node.py | 초기 D/src/rosy_control의 대응 위치 → 최종 D/src/rosy_core/rosy_core/web/ 및 api/ | 기능별 이관 후 별도 웹 entrypoint를 최종 배포에서 제외 |
| S/watch.py, watch_node.py | 초기 내부 패키지 유지 + D/src/rosy_core/rosy_core/system/·diagnostics/ 연계 | 장치별 검사와 OS 공통 상태 소유권 구분 |
| S/tools/의 재현·시뮬레이션 도구와 필요한 map/ 자산 | D/src/rosy_control/tools/·map/의 선별 파일 | test import·fixture·경로 참조로 선정, 설치 리소스 포함 여부 검사 |
| S/docs/의 보정·운영·검증 근거 | D/docs/deployment/ 및 D/docs/plans/의 이관 문서 | 과거 증거는 버전·날짜 표시. 새 장치 결과로 재사용 금지 |
| S/tools/deploy/** | D/deploy/robot·release의 기존 기능과 대응 | 스크립트 통째 활성화 금지; OS 배포로 기능 흡수 |
| .git·캐시·build/install/log·로컬 비밀정보 | 이전 제외 | OS 경로 독립 검사와 비밀정보 검사 |

파일별 대장은 원본 상대 경로, 목적지, 원본 SHA-256, 역할, 처리(이전/병합/참조보존/제외), 사유, 검증 항목을 갖는다. Git HEAD만으로 dirty source를 대표하지 않는다. 원본은 고정 snapshot에서 읽으며 사용자 WIP는 수정하지 않는다.

## 3. 의존성과 작업 단위

순서: T0 → T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8.
T5의 웹 기능 대조표는 T1부터 작성 가능하다. 하드웨어 의존성 조사는 T0부터 병행하되 모터가 동작하는 검증은 명령·안전 gate 이후다.

각 작업은 계획된 작은 변경으로 분리하고 기존 동작 회귀를 확인한 후 다음으로 넘어간다. 아래 테스트 추가는 파일 이동 자체를 복제하는 테스트가 아니라 독립 빌드·명령권·실패 처리·배포 계약을 검증하기 위한 것이다.

### T0. 원본과 목적지 기준선 고정
**생성:** D/docs/plans/2026-09-12-control-absorption-inventory.csv, D/docs/plans/2026-09-12-control-absorption-results.md.
1. 두 저장소 HEAD·status·worktree를 확인하고 구현용 OS 격리 worktree를 만든다.
2. 원본 tracked·untracked 파일과 외부 참조를 읽어 선별 snapshot·해시 목록을 만든다.
3. 11개 entrypoint, 10개 launch, 설정, 테스트 fixture, 장치/카메라/LCD 의존성을 대장에 연결한다.
4. 원본 전체 test suite를 실행하여 실패·skip·환경 의존성을 기록한다.
**명령:** S에서 python -m pytest test/ -q.
**완료:** 이전 범위의 모든 파일에 처리와 사유가 있고, 원본 기준선 결과를 재현할 수 있다.
**복구:** 아직 runtime 변경 없음. snapshot 기록을 정정할 때 버전을 새로 남긴다.

### T1. OS 내부 패키지와 테스트 편입
**생성:** D/src/rosy_control/ 아래 위 대장의 보존 대상.
**생성 시험:** D/test/test_control_absorption_package.py.
1. 대장에 따라 선택 파일을 복사한다. 원본 .git와 캐시·장치 데이터는 제외한다.
2. import 경로를 유지하고 OS 내부 설치 메타데이터·리소스 누락을 수정한다.
3. OS 소스만으로 테스트를 수집한다. source directory의 symlink·editable install로 통과시키지 않는다.
4. 소스와 테스트 변경 전후 결과 차이를 원본 기준선과 대조한다.
**명령:** D/src/rosy_control에서 python -m pytest test/ -q.
**추가 검증:** Linux clean OS checkout에서 colcon build --base-paths src --packages-up-to rosy_control; 설치 overlay만으로 import와 entrypoint 조회.
**완료:** 원본 경로 없는 OS checkout에서 빌드/테스트 가능. 기본 OS launch에서는 아직 이식된 구동 노드를 자동 활성화하지 않는다.
**복구:** OS의 추가 패키지 변경만 되돌릴 수 있는 단위로 유지한다.

### T2. ROS 그래프·설정·보정 경계 정리
**수정:** D/src/rosy_control/launch/, config/, *_node.py, safety/node.py, calibration_atomic.py, calib_node.py.
**생성:** D/test/test_control_absorption_graph.py, D/src/rosy_control/test/test_os_calibration_storage.py.
1. 절대 토픽·frame·파라미터 이름을 조사하고 OS namespace·frame_prefix 규칙에 매핑한다.
2. 기존 Nav2와 Control의 goal/route/session 차이를 표로 정리한다. 로봇 하나당 활성 주행 backend 하나를 선택하도록 설계한다.
3. config 기본값→장치 overlay→보정 데이터의 우선순위와 쓰기 경로를 확정한다. 패키지 share나 읽기 전용 이미지에 보정값을 쓰지 않는다.
4. 보정 revision·장치 식별·실효 기구값·freshness와 최종 gate acknowledgement를 보존한다.
5. 손상 보정·쓰기 실패·이전 schema 복구·장치 교체·재부팅 시 준비 상태를 검증한다.
**명령:** D에서 python -m pytest test/test_control_absorption_graph.py src/rosy_control/test/test_os_calibration_storage.py -q.
**완료:** 두 로봇 namespace가 분리되고 보정 상태를 소프트웨어 버전과 구분하여 복구할 수 있다.
**복구:** 이전 설정/보정 원본을 보존한다. 다운그레이드 불가 schema는 적용 전에 거절한다.

### T3. 명령 중재와 안전 정책 흡수
**수정:** D/src/rosy_core/rosy_core/command/manager.py, safety/manager.py, bridge/ros_bridge.py; D/src/rosy_control/rosy_control/safety/, calibration_atomic.py와 명령 발행 노드.
**생성:** D/src/rosy_core/test/test_control_absorption_safety.py; 내부 제어 계약 문서.
1. CORE manual/navigation/Fleet/estop과 Control cliff/tilt/pickup/obstacle/localization/보정 제한을 비교한다.
2. 새 통합 안전 판단을 ROS 없는 함수로 시험할 수 있도록 추출하고 기존 판단과 동일 입력으로 비교한다.
3. 선택된 모든 명령에 최종 안전 제한을 적용하고 CommandManager/RosBridge만 실제 모터 토픽을 발행하게 한다.
4. Control의 기존 gate는 최종 모터 발행 역할을 제거/비활성화한다. 판단·감지 기능은 보존한다.
5. 요청 식별·유효시각·선택 결과·최종 제한 결과를 연결한다. 보정 trial이 자신의 실제 선택·제한 결과를 확인하도록 acknowledgement를 이전한다.
6. 감지기/중재기 단절, stale/nonfinite 입력, 자동→수동 전환, estop 해제, 재기동을 시험한다.
**핵심 설계 제약:** 후보 명령을 평가한 결과가 다른 최신 명령에 적용되면 안 된다. 비동기 판단이면 요청/결과 일치와 만료를 검사한다. 동기 판단이면 제어 주기 내 처리시간을 측정한다. 최종 방식은 구현 계약에 기록한다.
**명령:** D/src/rosy_core에서 python -m pytest test/test_control_absorption_safety.py test/test_core_logic.py test/test_api.py -q.
**실행 검증:** 격리 ROS에서 실제 motor command topic의 publisher 1개, 센서/명령 timeout·모터 deadman을 확인.
**완료:** 모든 명령원의 안전 우회가 없고 최종 발행권·보정 acknowledgement가 일치한다.
**복구:** 통합 runtime을 비활성화하고 core로 복귀. 이전/신규 최종 발행자를 동시에 켜지 않는다.

### T4. 기존 주행 기능을 CORE에 연결
**수정:** D/src/rosy_core/rosy_core/navigation/manager.py, bridge/, capability.py; D/src/rosy_control/rosy_control/goal_node.py, wander/, control/navigation_session.py.
**생성:** D/src/rosy_core/test/test_control_absorption_navigation.py.
1. 기존 CORE 목표/취소/상태 계약에 Control 실행 backend를 연결한다.
2. 경로 생성과 실제 이동 완료를 구분하고 session/goal 결과를 공통 상태·사건으로 전달한다.
3. 안전 경로가 있을 때 재계획·우회하는 기존 동작을 보존한다.
4. Nav2와 Control 간 활성권 충돌, 만료 route, 취소 후 늦은 결과, 재시작을 시험한다.
**명령:** D/src/rosy_core에서 python -m pytest test/test_control_absorption_navigation.py test/test_operational_journey.py -q.
**완료:** CORE 요청→단일 backend→안전 중재→모터→실제 상태 피드백 경로를 격리 ROS에서 재현한다.

### T5. 웹·정비·진단 흡수
**수정:** D/src/rosy_core/rosy_core/api/, web/, system/, diagnostics/; D/src/rosy_control/setup.py·launch의 웹/감시 진입.
**생성:** D/docs/plans/2026-09-12-control-web-parity.md, D/src/rosy_core/test/test_control_absorption_api.py.
1. Control의 /state.json·navigation·goal·보정·카메라·지도·정비 동작을 기존 CORE 화면/API와 대조한다.
2. 기존 계약으로 표현 가능한 기능부터 이관한다. 신규 공개 계약이 필요하면 docs/reference와 protocol/schemas.py를 함께 변경한다. 기존 Control URL을 새 OS API로 단순 노출하지 않는다.
3. 작업자·정비자·관리자 권한과 현재 세션 반영을 확인한다.
4. graph/watch·관측 freshness·보정 revision·실행 결과를 OS 진단으로 연결한다.
5. OS 배포에서 별도 web_node 서버를 제외하고 운영 기능 누락 여부를 검증한다.
**명령:** D/src/rosy_core에서 python -m pytest test/test_control_absorption_api.py test/test_dashboard.py test/test_diagnostics_api.py -q.
**브라우저:** 기존 D/test/test_dashboard_browser.py 실행 환경을 사용하여 실제 허용/거절·단절·중복 클릭·상태 확인. 단순 API 성공으로 대체 불가.
**완료:** 운영·정비 기능 대조표가 충족되고 외부 조작 경로는 CORE로 통일된다.

### T6. OS 이미지·기동·CI·릴리스 편입
**수정:** D/deploy/robot/Dockerfile, compose.yaml, runtime-mode.sh, config/; D/.github/workflows/ci.yml; 필요한 deploy/release·image 계약.
**생성:** D/test/test_control_absorption_runtime.py.
1. 기존 Dockerfile의 명시 COPY와 packages-select에 필요한 내부 패키지·의존성을 추가한다. CORE 컨테이너에 장치 권한을 주지 않는다.
2. 현재 이미지에 포함되지 않은 ADC/IMU/LCD·Picamera2/libcamera 의존성을 장치별로 검증한다. 설치 성공과 카메라 캡처 성공을 분리한다.
3. hardware 등 기존 모드의 기능 조립을 확장한다. 새 모드를 임의로 추가하지 않으며 기존 기동 소유 위치를 확인한다.
4. capability는 해당 구성에서 실제 준비된 기능만 표시한다.
5. CI에 흡수 테스트와 노드 boot/ROS 계약을 포함한다. 해당 신규 gate 실패를 continue/|| true로 숨기지 않는다.
6. bundle에 코드·설정·보정 호환 정보, rollback 가능한 이전 상태를 기록한다.
**명령:** D에서 python -m pytest test/test_control_absorption_runtime.py test/test_robot_runtime.py test/test_release_updater.py -q.
**이미지 검증:** native ARM64 build 및 실제 Pi camera/IMU/ADC/LCD 구성 확인. full OS A/B는 범위 밖.
**완료:** OS artifact만으로 설치·기동·업데이트·core 복구가 가능하고 원본 저장소를 참조하지 않는다.

### T7. Pi 기능 인수
**수정 기록:** D/docs/plans/2026-09-12-control-absorption-results.md.
1. source SHA·artifact digest·장치 설치 버전·profile·보정을 기록한다.
2. 감지 전용 기동에서 카메라·IR·초음파·IMU·LiDAR·좌표·watch를 확인한다.
3. 통제된 공간에서 수동 정지·estop·센서 단절·보정·주행·우회·취소·재시작을 검증한다.
4. 웹 정비·진단 수집·이전 bundle 복구·보정 호환 실패를 재현한다.
**완료:** 선택한 장치 프로파일의 기존 기능 동등성과 안전/복구 조건을 실측 증거로 인수한다. 하드웨어가 없으면 이 단계는 HOLD이며 문서/CI 통과로 대체하지 않는다.

### T8. 흡수 종료와 유지보수 전환
1. 원본 runtime을 실행하지 않은 상태로 OS 단독 운영을 재검증한다.
2. OS 배포에서 구 Control 서버·기동 스크립트 참조를 제거한다.
3. 기존 기능별 OS 담당·테스트·runbook·보정 위치·복구 절차를 확정한다.
4. 원본은 provenance/복구 자료로 보존하고 개발 기준을 OS로 전환한다.
**완료:** OS checkout→build→install→운영→정비→rollback이 원본 프로젝트 없이 재현된다. 소스 병합·원격 발행·Pi 설치·현장 인수는 별도 상태로 보고한다.

## 4. 유지보수와 회귀 기준
- 이전 완료는 파일 복사량이 아니라 기능 대장·독립 빌드·단일 명령권·웹 동등성·실물 복구로 판단한다.
- 원본 108개 test 파일은 전부 대장에 등록하되 삭제/병합/비적용에는 이유를 남긴다. 테스트 개수 유지 자체를 품질 목표로 삼지 않는다.
- 결함 수정과 순수 이전은 변경 단위를 분리한다. 기준선 실패를 숨기기 위해 테스트를 지우지 않는다.
- 보정은 장치별 데이터다. OS 업데이트가 보정·신원을 초기화하거나 모터를 자동 재활성화하지 않아야 한다.
- 장치 교체·모델 변경·카메라 위치 변경에 따른 재보정/재인수 범위를 runbook에 명시한다.
- 기존 선택 테스트 266개 결과는 [구조 문서](2026-09-12-rosy-os-system-architecture-roadmap.md)의 흡수 전 기록이다. 신규 흡수 결과로 재사용하지 않는다.

## 5. 착수와 일정 기준
첫 구현 묶음은 T0+T1, 다음은 T2+T3, 이후 T4→T5→T6→T7→T8이다. 각 묶음은 검토 가능한 변경으로 남기고 해당 검증을 통과한 후 다음 작업을 진행한다.

확정이 필요한 기술 항목은 카메라 실행 위치·장치 의존성, 주행 backend 선택 방식, 최종 안전 판단 전달 방식, 보정 schema/저장 위치다. 제품 방향은 확정되었으며 이 항목들은 담당 구현자가 현재 계약과 벤치 근거로 결정할 기술 작업이다.

기간은 T0에서 기준선·의존성·기존 실패와 실물 접근 조건을 확인한 뒤 산정한다. 이번 문서 작성은 코드 흡수나 장치 변경 승인을 수행한 것으로 기록하지 않는다.
