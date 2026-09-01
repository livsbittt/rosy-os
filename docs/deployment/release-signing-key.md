# ROSY 릴리스 서명 키 운용

- **Document ID:** ROSY-DEPLOY-SIGNKEY-001
- **Status:** v1
- **Related:** `docs/plans/2026-09-01-rosy-os-v1-image-release-design.md` §7.4/§9.1,
  `deploy/release/signing.py`

## 1. 이 키가 무엇을 결정하는가

장비는 릴리스를 받으면 `SHA256SUMS`에 대한 Ed25519 detached signature를 먼저
검증하고, 통과한 뒤에야 개별 파일 checksum을 확인한다. 즉 **이 키를 가진 사람이
그 장비에 무엇이든 설치할 수 있다.** 컨테이너 이미지, systemd unit, 업데이트
스크립트가 모두 이 서명 하나 뒤에 있다.

v1은 신뢰 키를 **하나만** 쓴다. 장비의 `/etc/rosy/trusted-release-keys/<key-id>.pem`
에 공개키가 있고 manifest의 `signing_key_id`가 그것을 가리킨다.

## 2. 두 가지 결과를 먼저 이해할 것

**키가 유출되면** 공격자가 서명한 번들을 장비가 정품으로 받아들인다. v1에는 온라인
키 폐기 경로가 없다. 대응은 새 신뢰 키를 담은 recovery 이미지를 만들어 **모든 장비를
물리적으로 다시 굽는 것**이다.

**키를 잃어버리면** 그 순간부터 어떤 릴리스도 서명할 수 없다. 현장의 모든 장비가
업데이트 불능이 되고, 복구는 역시 새 키를 담은 recovery 이미지를 물리적으로 굽는
것뿐이다.

두 실패의 복구 비용이 같고, 둘 다 현장 방문을 요구한다. 그래서 백업과 접근 통제를
둘 다 진지하게 다뤄야 한다. 어느 한쪽만 잘해도 소용이 없다.

## 3. 생성

서명 전용 환경에서만 생성한다. 빌드 호스트도, 개발 PC도, 저장소도 아니다.

```bash
umask 077
openssl genpkey -algorithm ed25519 -out rosy-release-2026-01.key
openssl pkey -in rosy-release-2026-01.key -pubout -out rosy-release-2026-01.pem
```

- `.key`가 개인키다. 이 파일은 서명 환경을 절대 떠나지 않는다.
- `.pem`이 공개키다. 이것만 이미지와 저장소에 들어간다.
- key id(`rosy-release-2026-01`)는 manifest의 `signing_key_id`와 장비의
  `/etc/rosy/trusted-release-keys/` 파일명에 함께 쓰인다. 소문자·숫자·하이픈만
  허용된다(`deploy/release/manifest.py`의 `_KEY_ID`).

## 4. 보관

**서명 환경**은 네트워크에서 분리된 전용 머신 또는 하드웨어 토큰이어야 한다.
최소 요건:

- 개인키 파일은 `0600`, 소유자는 서명 작업 계정.
- 서명 환경에는 빌드 산출물을 반입만 하고, 개인키는 반출하지 않는다.
- 서명 작업 로그(언제, 어떤 release_id, 어떤 git revision에 서명했는지)를
  남기고 일반 artifact와 **분리 보관**한다.

**금지 사항** — 아래는 CI가 기계적으로 막는다(`test_release_boundary_guards.py`,
`test_release_signing.py`):

- 저장소에 개인키를 커밋하는 것
- 컨테이너 이미지나 SD 이미지에 개인키를 넣는 것
- 빌드 호스트에 개인키를 두는 것
- `.key` / `.pem` / `id_ed25519` 형태의 파일을 추적 대상에 넣는 것

## 5. 백업

키 분실이 유출과 같은 비용을 갖기 때문에 백업은 선택이 아니다.

- 최소 2부를 서로 다른 물리적 장소의 오프라인 매체에 보관한다.
- 각 사본은 봉인하고 개봉 이력을 기록한다.
- 복구 절차를 **연 1회 실제로 리허설한다.** 읽히지 않는 백업은 백업이 아니다.
- 백업 매체에는 공개키와 key id도 함께 넣어, 어떤 키인지 나중에 식별할 수 있게 한다.

## 6. 교체와 폐기

v1의 온라인 키 rotation은 비범위다. 교체 경로는 하나뿐이다.

1. 새 키를 서명 환경에서 생성한다(§3).
2. 새 공개키를 담은 **recovery 이미지**를 빌드한다.
3. 각 장비를 그 이미지로 다시 굽는다.
4. 이후 릴리스는 새 key id로 서명한다.

즉 키 교체는 소프트웨어 업데이트가 아니라 현장 작업이다. 키를 만들 때 이 사실을
전제로 보관 수준을 정해야 한다.

## 7. 릴리스 서명 절차

```bash
# 서명 환경에서
python3 deploy/release/sign_release.py dist/2026.09.01-001 \
    --private-key /secure/rosy-release-2026-01.key
```

현재 `deploy/release/signing.py`가 제공하는 것:

- `build_sha256sums(root, paths)` — 경로 오름차순 checksum 목록(LF, 정확한 바이트)
- `sign_checksums(sums, private_key)` — raw Ed25519 64바이트 서명을 base64로
- `verify_release_files(root, public_key)` — 서명 먼저, 그 다음 파일 checksum

`sign_release.py` CLI 자체는 WP-6에서 이미지 파이프라인과 함께 붙인다. 그때까지는
위 함수를 직접 호출한다.

## 8. 검증 순서를 바꾸지 말 것

`verify_release_files`는 **서명 → checksum** 순서를 강제하고, 서명이 실패하면
파일 해시를 아예 계산하지 않는다. 순서를 뒤집으면 다음 공격이 통한다.

1. 공격자가 payload를 바꾼다.
2. 바뀐 payload에 맞게 `SHA256SUMS`를 다시 만든다.
3. checksum을 먼저 보는 구현은 "모든 파일 정상"을 보고한다.

서명만이 이것을 잡는다. 그래서 서명이 실패했을 때 checksum 결과를 함께 보고해서도
안 된다 — 신뢰할 수 없는 목록에 대한 "정상"은 오해를 만든다. 이 동작은
`test_payload_is_not_hashed_against_an_untrusted_checksum_list`가 고정한다.
