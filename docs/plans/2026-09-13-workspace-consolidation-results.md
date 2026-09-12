# Rosy OS 실제 폴더·개발 기준 통합 결과

작성일: 2026-09-13.

## 원인

T0·T1 흡수, ADR D-37~D-44, 첫 보정 노드 수정은
`feat/rosy-control-absorption` worktree에만 존재했다.
`Rosy OS/main`은 c5bc064에 머물렀고 `Rogic/Rosy Control`이 원래 위치에 남아 있었다.
따라서 사용자에게 보이는 기본 폴더는 실제로 정리되지 않은 상태였다.

## 조치

- main의 tracked/untracked WIP 23개를 SHA-256으로 기록했다.
- 충돌하는 미추적 흡수 초안 1개를 archive로 보존한 뒤 main을 4f5365e로 fast-forward했다.
- 이 시점에 기존 WIP 23개가 main 또는 archive에서 바이트 단위로 보존됐음을 확인했다.
- 원본 Rogic 5,838개 파일(255,945,231 bytes)을 archive/legacy-rogic-20260913으로 옮겼다.
- Windows 긴 경로 제한으로 부분 이동이 중단됐으나, 이동 전 manifest를 기준으로 양쪽을 비교해
  남은 4,897개 파일을 확장 경로로 옮기고 전체 5,838개 해시 일치를 확인했다.
- 원본 Control의 Git 저장소는 archive 안에서 여전히 clean main이다.
- 비어 있던 Rosy Fleet 디렉터리는 코드가 없는 placeholder였으며 구현 코드는
  `src/rosy_fleet`에 그대로 있다.
- 루트의 이전 조사 메모는 archive에 보존하고 개발 진입 README와 현재 실행 계획을 만들었다.
- 패키지 README의 독립 Control 제품·옛 배포 도구 안내를 OS 기준으로 수정했다.
- main에 미추적 상태였던 조사·평가 문서 12개를 작업 브랜치에 편입하고,
  현재 ADR/실행 결과가 우선한다는 안내와 편입된 소스 링크를 연결했다.

## 증거와 범위

원본 이동 후 실제 main에서 패키지 소유권 시험 4 passed, Control 전체 회귀
907 passed·11 skipped를 확인했다. 추가 skip 1개는 Windows에 ROS가 없어 건너뛴
namespace 시험이며 이전 ROS Jazzy 컨테이너에서 통과한 별도 증거가 있다.
조사·설계·README의 내부 링크 171개가 유효하고 UTF-8 대체 문자가 없음을 확인했다.

workspace의 `archive/folder-transition-20260913/main-before.json`과
`legacy-files.json`은 파일별 원본 hash를 기록한다. 이 archive는 로컬 provenance이며
OS runtime·빌드·테스트의 의존 대상이 아니다. 원본 자격 증명·캐시·Git 저장소를 새 OS 커밋에 넣지 않는다.

다른 작업자의 IMU 변경은 별도 WIP로 유지한다. 원격 push, artifact 발행,
장치 설치와 실물 안전 인수는 이 폴더 정리 결과에 포함하지 않는다.
T2~T8 상태는 [흡수 실행 결과](2026-09-12-control-absorption-results.md)를 따른다.
