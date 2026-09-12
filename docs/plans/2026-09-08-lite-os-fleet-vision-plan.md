# ROSY Lite OS · 관제 · 비전 확장 Implementation Plan

> 2026-09-13 편입 안내: 이 문서는 작성 당시의 조사·평가 근거다. 현재 제품 경계와 구현 순서는 [ADR D-37~D-44](../reference/ROSY%20ADR%20Log.md), [흡수 실행 계획](2026-09-12-rosy-control-absorption-plan.md), [최신 실행 결과](2026-09-12-control-absorption-results.md)를 우선한다. 조사 당시의 미실행·별도 Control 표기는 현재 배포 상태를 뜻하지 않는다.

> 실행 시 `executing-plans` 스킬을 사용해 단계별로 구현·검증한다. 이 문서는 계획이며 구현 완료 보고가 아니다.

**Goal:** Pi 5용 공통 SD 이미지에서 수동 이름·번호·SSH 설정 없이 관제 등록을 완료하고, 검증된 비전 기능을 선택적으로 실행한다.

**Architecture:** Raspberry Pi OS Lite 64-bit를 호스트 기본 후보로 사용하고 ROSY의 ROS 실행환경은 Ubuntu Noble/Jazzy ARM64 컨테이너로 고정한다. 중앙 Fleet 서비스·웹은 별도 PC/서버에 두며, 비전과 로컬 화면 기능은 공통 기반에 추가하는 배포 구성으로 관리한다.

**Tech Stack:** Raspberry Pi OS Lite Trixie, systemd, NetworkManager, Docker Compose, ROS 2 Jazzy, CycloneDDS, FastAPI, OpenCV, 하드웨어별 카메라·AI 런타임.

작성: 2026-09-08. 상태: 계획 작성 완료 / 이미지·중앙 관제·확장 기능 구현 및 실기 검증 대기.

## 1. 판단과 전제

**Lite는 로봇의 ROS 실행·관제 연결·웹 API 제공을 위한 적합한 기본 구성으로 판단한다.**
데스크톱이 없다는 이유로 원격 관제나 OpenCV 처리가 불가능해지는 것은 아니다.
다만 이 판단은 구조·공식 지원 근거에 따른 것으로, 실제 하드웨어의 성능·안정성을 검증했다는 의미는 아니다.

Lite 선택 목적은 무조건 최소 용량이 아니라 필요한 서비스를 명시적으로 구성하는 것이다.
기능·드라이버 호환성을 먼저 확보하고 저장공간·메모리·부팅 비용을 그다음 최적화한다.
필요한 패키지는 이미지 또는 검증된 확장 묶음에 포함해 사용자가 설치 후 개별 설정하지 않게 한다.

관제의 의미를 구분한다.

| 대상 | 배치 | 판단 |
|---|---|---|
| 로봇 API·로봇별 웹 대시보드 | 각 Pi의 rosy_core | Lite와 양립하는 기존 구조 |
| 여러 로봇의 등록·상태·작업 관리 | 별도 PC/서버의 중앙 Fleet | OS와 별개로 서버·웹 구현 필요 |
| 관제 웹 열람 | 운영 PC·태블릿 브라우저 | 로봇 Pi의 데스크톱 불필요 |
| Pi 자체 HDMI 화면·RViz·영상 창 | 선택적 로컬 화면 구성 | 그래픽 환경을 추가해 검증 |

관제 서버까지 로봇 Pi 한 대에 합치는 구성은 이 계획의 기본값이 아니다.
별도 Pi를 관제 서버로 쓸 수 있는지는 서비스 구성·로봇 수·영상 부하를 별도로 측정해 결정한다.
중앙 관제의 구현 완료나 특정 대수 수용 성능을 Lite 선택만으로 보장하지 않는다.

## 2. 목표 사용자 흐름

`공통 SD 기록 → 전원 켜기 → 네트워크 연결 → 관제 발견 목록 → 일괄 등록 → 자동 이름 확정 → core 준비 완료`

장비별 hostname·RobotNumber·토큰 입력과 SSH 설치 명령을 정상 흐름에서 제거한다.
유선 네트워크부터 검증한다. Wi-Fi는 현장 정보를 한 번 입력해 여러 SD에 적용하는 설치 경로로 확장한다.
신원·자동 이름·동시 등록·SD 교체 정책은 [자동 등록 설계](2026-09-08-automatic-device-onboarding-design.md)를 따른다.
`core 준비 완료`, `센서 준비`, `위치 추정 준비`, `주행 허용`은 구분한다.

## 3. 공통 기반과 확장 구성

| 구성 | 포함 대상 | 경계 |
|---|---|---|
| 공통 OS 기반 | Pi 커널·펌웨어, 네트워크·시간 동기화, 등록 서비스, 업데이트·복구 | 장비 키·신원은 첫 부팅 생성, 공용 이미지에 미포함 |
| ROS 공통 실행 | Jazzy, CycloneDDS, rosy_core, 기존 IO 프로필 | core는 비root, 외부 제어의 단일 게이트웨이 |
| 비전 확장 | OpenCV, 필요한 contrib 모듈·영상 입출력·카메라 어댑터 | 별도 인지 프로세스, CORE에 추론 부하 집중 금지 |
| 가속기 확장 | 지원 보드의 호스트 드라이버·런타임·펌웨어·모델 | 호스트와 컨테이너 버전 호환 검사 |
| 화면·개발 확장 | 필요한 GUI·RViz·미리보기·진단 도구 | 공통 실행 버전 유지, 기능 요구가 있을 때 포함 |

위 구성은 배포 묶음이며 `ROSY_RUNTIME_MODE`에 새로운 값을 추가하라는 뜻이 아니다.
비전 소유권은 [기존 비전 설계](2026-09-05-vision-accelerator-shield-design.md)와 정합한다.
CSI·AI 런타임을 모두 하나의 Noble 컨테이너에 넣을 수 있다고 가정하지 않는다.
현재 하드웨어 프로필의 SLAM·비전 미구현 상태를 OS 선택으로 완료 처리하지 않는다.

## 4. 구현 단계

### 단계 1: 지원 구성과 합격 기준 고정

작업 파일: 이 문서, `docs/plans/2026-09-08-os-platform-sources.md`,
`docs/deployment/pinky-pro-board-support.md`, `deploy/image/inputs.lock.yaml`.

1. 첫 지원 하드웨어를 Pi 5와 현재 로봇 프로필로 제한하고 카메라·가속기 대상 모델을 명시한다.
2. 카메라 해상도·FPS·모델·관제 동시 접속 수·지연 목표를 시험표에 먼저 작성한다. 미정값은 통과로 처리하지 않는다.
3. OS·커널·컨테이너·OpenCV·ROS 영상 라이브러리·카메라 SDK·가속기 버전의 호환 표를 작성한다.
4. 후보가 공식 제공된다는 사실과 실제 검증 상태를 구분한다. `verified: true`는 해당 검증 후에만 기록한다.

완료 기준: 재현할 버전과 장비 조합, 측정 방법, 합격 기준이 모두 명시됨.

### 단계 2: PC에서 등록·관제 흐름 구현

계약 검토: `docs/spec/ROSY FLEET SRS.md`, `docs/reference/ROSY API & Protocol Reference.md`,
`docs/reference/rosy-host-agent-contract.md`, `src/rosy_core/rosy_core/protocol/schemas.py`.
재사용 검토: `src/rosy_fleet/`, `src/rosy_gz_sim/launch/gz_multi.launch.py`.

1. 기존 등록 설계에 따라 영속 등록부와 등록용 가상 호스트를 만든다. Fleet 서비스의 저장 위치는 구현 착수 시 별도 소유권 설계에서 확정한다.
2. 중복 요청·동시 번호 배정·서버 재시작 실패 시험을 먼저 만들고 최소 구현으로 통과시킨다.
3. 발견·일괄 등록·자동 이름·실패 사유·재시도 화면을 구현하고 실제 브라우저로 3대를 등록한다.
4. 동일 신원 유지, 한 대 연결 끊김, 재연결, 모터 미기동을 확인한다.

완료 기준: 사용자가 이름·번호·토큰을 입력하지 않고 가상 장비 3대 등록 완료. 중앙 웹 기능의 실제 동작 증거 확보.

### 단계 3: 호스트 첫 부팅·공통 이미지 연결

작업 파일: `deploy/image/build-image.sh`, `deploy/image/inputs.lock.yaml`,
`deploy/image/verify-inputs.sh`, `deploy/image/verify-artifacts.sh`,
`deploy/robot/install-pi.sh`, `deploy/release/image_checks.py`.
시험: `test/test_image_pipeline.py`, `test/test_image_checks.py`, `test/test_dds_identity_contracts.py`.

1. 개인화되지 않은 이미지 조건과 번호 없는 CORE 기동 금지 조건에 대한 실패 시험을 작성한다.
2. 등록용 호스트 서비스와 원자적인 신원 적용을 구현한다. 적용 중단 후 재개 시험을 먼저 통과시킨다.
3. 네이티브 ARM64 제작 환경에서 버전을 고정하고 rpi-image-gen layer/hook 및 실제 이미지 생성을 구현한다.
4. 사전 빌드 ROSY 이미지를 적재하고 결과 이미지의 비밀값 부재·계정·버전·파일 무결성을 검사한다.
5. SD 기록·검증 후 첫 Pi에서 유선 자동 등록과 core 기동을 시험한다.

회귀 명령: `python -m pytest test/test_image_pipeline.py test/test_image_checks.py test/test_dds_identity_contracts.py -v`.
완료 기준: 이미지 검사 통과와 실제 Pi 첫 부팅 증거를 각각 확보. 파일 생성만으로 출하 가능 판정 금지.

### 단계 4: OpenCV·카메라·AI 기능 검증

작업 기준: `docs/plans/2026-09-05-vision-accelerator-shield-design.md`의 모듈·장치 권한 경계.
연결 검토: `deploy/robot/Dockerfile`, `deploy/robot/compose.yaml`, `deploy/robot/config/capabilities.hardware.yaml`.

1. CPU OpenCV 경로부터 실제 카메라 획득·처리·ROS 영상 변환·관제 표시를 검증한다.
2. 필요한 videoio 백엔드와 contrib 모듈을 확인한다. GUI 없는 패키지를 모든 구성에 일괄 강제하지 않는다.
3. CSI 및 가속기는 각 호스트 드라이버/사용자 공간 조합으로 별도 검증한다.
4. 비전과 Nav2 동시 부하에서 프레임 손실·지연·메모리·온도·제어 주기를 기록한다.
5. 비전 종료·재시작·입력 단절 시험으로 CORE와 안전 경로의 독립성을 확인한다.

완료 기준: 단계 1의 목표 통과, 실패 시 명시적 unavailable 상태, 비전 미설치 상태에서도 core 정상 기동.

### 단계 5: 실제 Pi 3대와 수명주기 검증

작업 파일: `docs/deployment/pi5-acceptance-checklist.md`, `docs/deployment/github-updates.md`,
`docs/deployment/raspberry-pi-wifi-image.md`.

1. 같은 이미지로 3대를 등록하고 이름·키·번호·데이터 충돌이 없는지 확인한다.
2. Pi 재부팅·관제 재시작·네트워크 단절 후 이름과 인증을 유지하는지 확인한다.
3. 런타임 업데이트·실패 롤백·전원 중단 복구 시 신원과 데이터 보존을 시험한다.
4. Wi-Fi 현장 정보 일괄 주입과 잘못된 정보의 복구 절차를 추가 검증한다.
5. 로컬 화면이 필요한 구성은 그래픽 환경을 포함한 별도 시험을 수행한다.

완료 기준: 장비별 증거를 남기고 코드·이미지·실기기 결과를 별도 판정. 합격한 조합만 지원 목록에 게시한다.

## 5. 결정 재검토 조건과 현재 상태

- 카메라/가속기 SDK가 다른 OS를 요구하면 Lite 우선안보다 해당 호환성을 우선한다.
- Pi 자체 화면이 제품 필수이면 그래픽 스택을 포함한다. 이것만으로 호스트 OS 계열을 바꿀 필요는 별도 판단한다.
- 전체 OS의 무인 원자 업데이트가 필수이면 이미지 레이아웃 확정 전에 A/B 또는 Ubuntu Core를 재평가한다.
- 성능 측정 없이 Lite가 더 빠르다거나 특정 로봇 수를 처리한다고 단정하지 않는다.

현재 판정: **Lite 기반 구성의 설계 타당성은 인정. 중앙 관제 구현·공통 이미지 제작·비전 및 실제 운용 수용 시험은 HOLD.**
이번 작업은 계획 문서 작성이며 코드 구현·OS 설정 변경·SD 기록·배포는 수행하지 않는다.

공식 근거와 비교 상세: [OS 조사 문서](2026-09-08-os-platform-sources.md).
OpenCV GUI/비GUI 구분: [OpenCV Python 공식 프로젝트](https://github.com/opencv/opencv-python).
Lite 카메라 지원: [Raspberry Pi 카메라 문서](https://www.raspberrypi.com/documentation/computers/camera_software.html).
