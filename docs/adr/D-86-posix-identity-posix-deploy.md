## D-86 POSIX identity 시험은 POSIX 호스트에서만 deploy를 찍는다

**Status:** Accepted (2026-09-17). D-79의 deploy 예외다.

**Context:** `test_dds_identity_contracts.py`는 Git Bash로 `lib.sh`를 소스로
한다. 이 Windows 세션은 임시 경로(`X:\DevTemp\...`)를 bash가 읽지 못해 13건이
실패했다. 그 실패로 deploy SOURCE를 HOLD로 내리면 호스트 계약이 있는 다른
시험까지 같이 무너진다. 반대로 실패한 채로 last_verified를 찍으면 D-79를
어긴다.

**Decision:** `require_robot_identity` bash 시험은 **POSIX(Git Bash가 `/` 임시
경로를 쓰는 환경, 또는 Linux)** 에서만 deploy `last_verified`를 채운다.
Windows에서 이 시험이 깨져도 deploy SOURCE GO(다른 계약)를 뒤집지 않는다.
다만 **그 호스트에서는 last_verified를 비운다.**

**Alternatives:** Windows 실패를 SOURCE HOLD로 쓰는 안은 계약 시험을 환경
결함과 섞는다. 실패를 무시하고 SHA를 찍는 안은 D-79 위반이다.

**Consequences:** STATUS.md deploy 행의 `uncommitted`는 이 결정이다. Linux CI
또는 Git Bash가 통과하면 그때 SHA를 넣는다.

**Validation / Transition:** `test/test_dds_identity_contracts.py`.
`deploy/progress.md` last_verified.

**References:** D-33, D-61, D-79.

---
