## D-146 unsigned ARM64 handoff는 검증 후에만 오프라인 서명 입력이 된다

**Status:** Accepted (2026-09-21).

**Context:** D-145 artifact의 외부 SHA-256만 확인하고 수동으로 압축을
해제하면 archive 경로 탈출, 링크/특수 파일, builder와 manifest의 identity
불일치, 미선언 파일, 변조된 OCI archive, 또는 amd64 image가 오프라인 서명
입력까지 도달할 수 있다. 서명은 입력의 출처와 구조가 먼저 검증되었을 때만
의미가 있다.

**Decision:** `import_unsigned_payload.py`가 canonical archive 이름과 외부
checksum을 먼저 확인하고, 제한된 임시 영역에서 member path/type/count/size를
검증한다. 이어 builder, manifest, provenance, 모든 payload hash와 두 Docker-save
config의 `linux/arm64` 및 image ID를 비교한다. 전부 통과한 뒤에만 출력
디렉터리를 원자적으로 노출한다. 이 도구는 private key 인수를 제공하지 않는다.

**Consequences:** importer JSON의 `ok: true`와 `signed: false`는 안전하게
오프라인 서명 단계로 전달할 수 있다는 뜻일 뿐 ARTIFACT 또는 G0 GO가 아니다.
오프라인 Ed25519 서명, `verify-publication`, matching public key, 장비 stage와
readback은 계속 필수다. 실패 시 완성 출력과 임시 payload를 남기지 않는다.

**Validation / Transition:** 실제 D-145 archive를 importer로 다시 검증해
release/revision/key ID, 17개 payload hash, CORE/IO `linux/arm64`를 확인하고,
그 JSON을 signed-bundle verification과 함께 커미셔닝 evidence에 보존한다.

**References:** D-53, D-66, D-140, D-145,
`import_unsigned_payload.py`, `pinky-pro-first-device-runbook.md`.

---
