## D-145 네이티브 ARM64 빌드는 unsigned artifact까지만 자동화한다

**Status:** Accepted (2026-09-21).

**Context:** D-66 네이티브 builder는 Linux aarch64 호스트에서만 실행되지만 개발
PC는 amd64이고 Pinky는 아직 네트워크에 연결되지 않았다. GitHub의 네이티브 arm64
리허설은 source build만 수행하므로 실제 `core`/`io` OCI 아카이브와 manifest를 남기지
않는다. 반면 개인 Ed25519 키는 개발 PC, 빌드 러너, 저장소에 둘 수 없다.

**Decision:** 수동 `build-arm64-payload.yml`은 고정된 `ubuntu-24.04-arm`에서 digest로
핀한 ROS base를 확인하고 기존 `arm64_release_builder.py`를 실행한다. 결과는 두 OCI
archive, runtime config, unsigned manifest, builder JSON을 하나의 `unsigned` archive와
SHA-256으로 묶어 7일간 Actions artifact로 보존한다. 워크플로 권한은
`contents: read`뿐이며 비밀키·서명 단계·release publication은 포함하지 않는다.

**Alternatives:** amd64/QEMU 산출물을 G0에 쓰는 방식은 D-66 위반으로 기각한다. GitHub
secret에 개인키를 넣어 온라인 서명하는 방식은 오프라인 키 경계를 깨므로 기각한다.
Pinky 자체에서 첫 빌드를 수행하는 방식은 장치 연결 전에는 불가능하고 커미셔닝 대상과
빌드 호스트를 혼합하므로 기본 경로로 삼지 않는다.

**Consequences:** native unsigned artifact가 생겨도 ARTIFACT와 G0는 HOLD다. 지정된
오프라인 서명 환경에서 bundle을 서명·검증하고, 신뢰 공개키를 장치와 publication
workflow에 등록해야만 signed release가 된다. Actions artifact는 7일 후 삭제되므로
서명 환경으로의 반입을 그 전에 완료해야 한다.

**Validation / Transition:** workflow 계약 테스트는 수동 trigger, native runner,
digest pin, builder 호출, unsigned 이름, checksum과 7일 retention을 고정한다. 실제
workflow run의 artifact와 checksum을 다운로드 검증한 뒤 오프라인 서명 단계로 넘긴다.

**References:** D-66, D-78, D-140, `arm64_release_builder.py`,
`release-signing-key.md`, `pinky-pro-first-device-runbook.md`.

---
