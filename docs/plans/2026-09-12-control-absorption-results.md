# Rosy Control → Rosy OS 흡수 실행 결과

작성일: 2026-09-12. 브랜치: `feat/rosy-control-absorption`.

## 현재 단계

- T0 원본과 목적지 기준선: 완료.
- T1 OS 내부 패키지와 테스트 편입: 완료.
- T2–T8 ROS 연결·명령권·웹·배포·Pi 인수: 미착수.

이번 변경은 Rosy Control의 Git 추적 소스 가운데 실행 패키지, 테스트, 설정,
launch, 웹 자원, 테스트가 직접 참조하는 도구·지도·검증 fixture를
`src/rosy_control`에 편입했다. 원본 저장소는 수정하지 않았다.

[파일별 이전 대장](2026-09-12-control-absorption-inventory.csv)은 원본 경로,
목적지, SHA-256, 역할, 처리 결과와 후속 검증 단계를 기록한다. 대장 생성 시점에
원본 Git 추적 파일 1,058개와 무시된 로컬 장치 증거 32개를 확인했다. T1에는
320개를 편입했고 738개 문서·legacy 배포 도구·과거 증거는 후속 기능 대조 대상으로 미뤘다.
무시된 장치 증거 32개는 범용 소스 fixture로 간주하지 않고 제외했다.

## 기준선과 검증

| 범위 | 결과 | 의미 |
|---|---:|---|
| 원본 Rosy Control 전체 테스트 | 907 passed, 1 skipped | 흡수 전 로컬 기준선 |
| OS 소유권 RED 시험 | 3 failed | `src/rosy_control` 부재로 기대대로 실패 |
| 편입 후 OS 소유권 시험 | 4 passed | package metadata·import·테스트·OS catalog 소유 확인 |
| 편입 후 Control 전체 테스트 | 898 passed, 10 skipped | 원본 checkout 없이 OS 내부에서 실행 |
| ROS Jazzy clean package build | 1 package finished | `ros:jazzy-ros-base` 컨테이너에서 colcon build, 설치 overlay import 확인 |
| 기존 OS CORE·배포 전체 기준선 | 1405 passed, 10 skipped, 27 failed, 27 errors | 흡수 전 Windows 기준선; Linux script·OpenSSL 부재 영향 포함 |

편입 후 skip 증가는 원본에서 Git에 포함하지 않았던 실물 카메라 artifact와
ROS message 환경에 의존하는 시험 때문이다. 이 차이를 통과로 숨기지 않으며 T6의
Linux/ROS CI와 T7의 Pi 인수에서 닫는다.

기존 OS 전체 기준선의 release signing/delivery 오류는 Windows PATH에서
`openssl`을 실행하지 못한 것이 주원인이었다. DDS identity·publication 일부는
Linux shell 전제도 포함한다. 이 결과는 흡수 전 발생했으며 이번 변경의 회귀로
분류하지 않는다. CORE 로직·API·운영 여정 선택 시험 68개는 별도 정상 권한
실행에서 통과했다.

## 현재 제품 상태

Rosy OS 저장소가 `rosy_control` 소스와 테스트를 소유하기 시작했다. 아직 OS
compose·이미지·CORE API·CommandManager에 연결하지 않았으므로 별도 Control
runtime 없이 Pi가 동작한다고 주장할 수 없다. 특히 기존 SafetyNode와 RosBridge의
최종 속도 발행 경로를 동시에 활성화하면 안 된다.

다음 작업은 T2의 namespace·설정·보정 경계와 T3의 단일 명령권·안전 정책
흡수다. 이 두 단계를 통과하기 전에는 편입된 legacy launch를 OS 기본 모드에
추가하지 않는다.
