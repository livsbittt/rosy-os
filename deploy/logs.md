# deploy logs

추가만 한다. 형식: [module harness 설계](../docs/plans/2026-09-15-module-harness-design.md) §4.2.
2026-09-15 이전 이력은 [Device 검증 계획](../docs/plans/2026-09-13-rosy-os-device-validation-implementation-plan.md)과 `git log -- deploy`를 본다.

## 2026-09-15 · uncommitted · docs(harness): start the deploy harness pilot
- 변경: `progress.md`, `logs.md`, 생성 `index.md` 추가. `AGENTS.md`에 기록 위치와 작업 순서 연결
- 증거: `python -m pytest test -q` 835 passed, 12 skipped (Windows + Git Bash/OpenSSL PATH, 미커밋 WIP 포함 작업 트리)
- gate 변화: 없음. 기존 SOURCE/LOCAL GO, ARTIFACT/DEVICE HOLD를 스냅샷으로 옮김
- 결정: D-61 Proposed
- 교훈: 없음

## 2026-09-15 · uncommitted · docs(harness): state excluded gates and rerunnable source evidence
- 변경: 리뷰 반영. ROS-SIM·FIELD를 N/A로 명시(물리 구동은 소비 모듈 gate), SOURCE에 재실행 명령 추가, `last_verified.commit`을 `uncommitted`로
- 증거: 미실행 — 기록 형식만 변경
- gate 변화: 없음 (누락 키를 N/A로 명시)
- 결정: 없음
- 교훈: 없음

## 2026-09-18 · uncommitted · feat(host-agent): structured network status, set_mode, connect (D-124)

- 변경: network.status 를 D-26 필드로 파싱. network.set_mode, network.connect 허용. PSK는 감사/응답에서 제거
- 증거: `python -m pytest test/test_host_agent.py -q`
- gate 변화: 없음. DEVICE HOLD 유지
- 결정: D-124
- 교훈: 없음

## 2026-09-21 · 1acb41a · feat(deploy): fail-closed Pinky commissioning

- 변경: G0-G5 순차 세션, 실제 release/readback JSON 유도, 증거 SHA-256,
  lock/CAS 원자 저장, SSH/console 런북, 유선/무선 인터페이스 검증 추가
- 증거: `python -m pytest test -q` -> 1001 passed, 13 skipped; 집중 169개,
  Python/Bash/PowerShell 구문 및 `git diff --check` 통과
- gate 변화: SOURCE/LOCAL GO 갱신. ARTIFACT/DEVICE는 signed ARM64 bundle과
  실제 Pinky Pro readback 전까지 HOLD, FIELD는 N/A 유지
- 결정: 없음
- 교훈: G0-G2는 작업자 요약이 아니라 stage manifest/install/readback 원문에서
  유도하고, G3-G5 미측정 템플릿은 검증을 통과하지 못해야 한다

## 2026-09-21 · c2bb799 · feat(release): native ARM64 unsigned payload builder

- 변경: native Linux aarch64/ARM64 Docker daemon/clean revision/digest-pinned ROS base를 강제하고 `core`/`io`를
  Buildx로 빌드한 뒤 linux/arm64, OCI revision label, immutable image ID를 검사한다.
  검사한 image ID로 Docker-save archive, runtime config, provenance, manifest를 원자적으로 만들며 private
  signing key는 받지 않는다. 기존 offline packager와 publication JSON 검증으로 연결했다.
- 증거: builder/publication/image/release/runtime/commissioning 집중 `516 passed, 8 skipped`;
  전체 `1035 passed, 13 skipped`;
  py_compile, flake8, `git diff --check` 통과. Windows 실제 CLI는
  `BUILD_HOST_OS`로 종료하고 payload를 만들지 않았다.
- gate 변화: SOURCE만 갱신. ARTIFACT는 native aarch64 실행과 실제 offline signature,
  DEVICE는 Pinky 설치/readback 전까지 HOLD다.
- 교훈: full SD-image 파이프라인의 미구현 상태와 update bundle builder를 구분하되,
  어느 쪽도 x86/QEMU 산출물을 G0 증거로 승격하지 않는다.

## 2026-09-21 · 6f6c515 · feat(deploy): capture Pinky connection evidence

- 변경: Windows peer verifier에 bounded optional batch SSH, API port/timeout, atomic
  no-overwrite JSON evidence를 추가했다. 성공은 선택 interface의 SSH 주소와 API/dashboard,
  실패는 stable code와 HOLD만 기록하며 원격 stderr·credential은 evidence에 넣지 않는다.
- 증거: 실제 PowerShell+fake SSH+loopback HTTP 시험을 포함한 집중 `81 passed`;
  전체 `1041 passed, 13 skipped`; PowerShell parser, py_compile, flake8,
  `git diff --check` 통과. 미연결 `192.168.4.1`은 4초 내 `SSH_ROUTE/HOLD`를 기록했다.
- gate 변화: SOURCE/LOCAL만 갱신. 연결 GO도 G0 artifact, DEVICE, FIELD를 대신하지 않는다.
- 교훈: 장치 미연결을 콘솔 timeout으로만 남기지 말고 재실행 가능한 구조화 evidence로
  남기되, 자동 subnet scan이나 host-key 우회로 장치 identity 경계를 약화하지 않는다.

## 2026-09-21 · uncommitted · feat(deploy): make physical G5 mapping evidence-bound (D-144)

- 변경: added an orthogonal `ROSY_NAVIGATION_BACKEND=localization|slam` selector for hardware runtime. SLAM selects its own capability/readiness profile, writable maps mount, and image packages for SLAM Toolbox plus MCAP recording; localization remains read-only and AMCL-based.
- 증거: focused hardware-mapping, commissioning, runtime, navigation, and CORE tests pass on Windows; the development image was built and its packages and launch arguments inspected.
- gate 변화: SOURCE/LOCAL evidence is refreshed. ARTIFACT and DEVICE remain HOLD until a signed native ARM64 bundle is installed and the physical Pinky G0-G5 session produces the required files.
- 결정: D-144.
- 교훈: a mapping API and a SLAM package are insufficient unless the runtime backend, writable persistence, readiness, raw telemetry, generated map pair, and final safe state are all bound into one commissioning session.

## 2026-09-21 · uncommitted · feat(release): export native ARM64 unsigned payloads (D-145)

- 변경: added a manual `ubuntu-24.04-arm` workflow that invokes the existing fail-closed builder, frees ephemeral image layers, archives the unsigned payload and builder JSON, and uploads the archive with SHA-256 for seven days.
- 증거: ARM64 builder plus workflow contracts and the combined root+CORE suite pass locally (`2021 passed, 24 skipped`). Native rehearsal run 35539577735 built on arm64 and exposed 11 environment-sensitive test failures; the two fixtures were made overlay-independent and are rerun after integration.
- gate 변화: SOURCE only. ARTIFACT remains HOLD until the native artifact completes and is signed and verified offline.
- 결정: D-145.
- 교훈: upload the immutable build handoff, not a mutable tag, and make `unsigned` impossible to overlook in both artifact and archive names.
