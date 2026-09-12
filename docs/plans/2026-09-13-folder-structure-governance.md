# Rosy OS 폴더 구조 정리 계획 및 결과

작성일: 2026-09-13. 상태: 1차 정리 완료, 운영 통합 게이트는 별도 진행.

## 목표

Rosy Control 흡수 이후 개발자가 한 번에 찾아야 하는 기준 경로를 고정한다.
문서·이미지·ARM64 절차가 서로 다른 루트에 흩어지지 않게 하고, 과거
upstream 자료는 실행 절차와 섞이지 않도록 provenance로 분리한다.

## 기준 구조

```text
Rosy OS/
├── src/                     ROS 2 패키지와 흡수된 rosy_control
├── deploy/                  이미지·릴리스·Pi 운영 스크립트
├── docs/                    저장소 문서의 유일한 기준 루트
│   ├── spec/                요구사항
│   ├── reference/           API·ADR·Host Agent 계약
│   ├── plan/                장기 WBS
│   ├── plans/               날짜별 설계·실행 기록
│   ├── deployment/          현재 Pi/ARM64 절차와 인수 체크리스트
│   ├── assets/              비실행 이미지·제품 자료
│   └── test/                검증 보고서
├── dock/                    충전 도크 펌웨어
└── test/                    호스트 배포·릴리스 계약 시험
```

`doc/`는 제거했다. `architecture.png`와 `rosy_pro_image.png`는
`docs/assets/`로 이동했고, 현재 ARM64 안내는
`docs/deployment/arm64-build-notes.md`로 작성했다. 기존 upstream clone 안내는
`docs/deployment/legacy-arm64-guide.md`에 경고와 함께 보존했다.

## 책임 경계

| 질문 | 기준 경로 |
|---|---|
| 제품 요구사항·공개 계약·결정은 어디에 있는가? | `docs/spec/`, `docs/reference/` |
| 진행 중인 설계와 흡수 증거는 어디에 기록하는가? | `docs/plans/` |
| Pi에서 지금 따라도 되는 절차는 어디에 있는가? | `docs/deployment/` |
| 그림이나 제품 사진은 어디에 있는가? | `docs/assets/` |
| ROS 코드와 테스트는 어디에 있는가? | `src/` 아래 각 패키지 |
| 예전 원본을 비교해야 하는가? | `archive/`와 Git 이력; 운영 입력으로 사용하지 않음 |

## 완료 조건과 잔여 작업

- 완료: 루트 `doc/` 제거, 자산·ARM64 문서 이동, README/AGENTS 경로 갱신,
  ADR D-45 기록, 옛 경로 참조 검색.
- 잔여: `rosy_control`을 운영 launch에 연결하는 T6 (package image absorption은 완료), 실제 ARM64
  build와 Pi 설치·readback, 카메라/OpenCV G2, Pinky Pro 물리 인수 G3/T7,
  OMX 모델·하중·hand-eye 결정. 폴더 정리만으로 이 게이트들은 통과하지 않는다.

검증 시에는 경로 존재·부재와 Markdown 링크를 확인하고 `git diff --check`를
실행한다. 이 문서의 구조 결정은 D-45에 기록했으며, 새 폴더를 추가할 때도
해당 책임 경계를 먼저 갱신한다.


## 2026-09-13 provenance follow-up

The consolidated source tree is now also the provenance source for Gazebo
motion evidence. measure_motion_contract.py discovers the local absorbed
package or a validated ROSY_SOURCE_ROOT; no runtime tool may depend on the
archived checkout or a historical temporary path. ADR D-49 and its four pure
tests record this rule. Archive files remain historical evidence only.


## 2026-09-13 active guide cleanup

The active src/rosy_control/CLAUDE.md and STEPS.txt now contain only Rosy OS
test, build, Device install, runtime, and readback procedures. Standalone
Control workspace commands remain only in the separate archive. ADR D-50 and
the package ownership contract protect this boundary.
