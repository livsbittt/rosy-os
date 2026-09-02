<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# docs

## Purpose

Governance documents (D-17): requirements, shared API/protocol contract, ADRs, implementation plan, dated design/execute plans, Pi deployment runbooks, and a Phase 1 test report. Requirement IDs are the cross-document keys, not section numbers.

## Key Files

None at this directory root — content lives in the subdirectories below.

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `spec/` | CORE and FLEET software requirements (see `spec/AGENTS.md`) |
| `reference/` | API contract, ADR log, Host Agent contract (see `reference/AGENTS.md`) |
| `plan/` | Implementation plan and Flask parity checklist (see `plan/AGENTS.md`) |
| `plans/` | Dated design + execute plans (see `plans/AGENTS.md`) |
| `deployment/` | Pi 5 runtime, Wi-Fi image, power bench, release keys (see `deployment/AGENTS.md`) |
| `test/` | P1 test report (see `test/AGENTS.md`) |

## For AI Agents

### Working In This Directory

- Do not put implementation code here. Specs constrain `src/`; deployment docs constrain `deploy/`.
- Changing API paths or envelope fields requires updating `reference/ROSY API & Protocol Reference.md` **and** `rosy_core/protocol/schemas.py` together (D-18).
- ADRs are append-only: mark old ones `Superseded`, add a new ID. Do not silently rewrite D-n.
- Dated files in `plans/` are the working design trail; `plan/ROSY Implementation Plan.md` is the WBS tracker.

### Testing Requirements

No automated tests. After doc edits, grep the code for the requirement IDs you changed and confirm tests still name them.

### Common Patterns

- Korean prose for governance docs; English identifiers (`SAF-005`, `D-22`).
- Design docs often come in pairs: `*-design.md` then execute plan `*.md`.

## Dependencies

### Internal

- Implementation: `src/rosy_core`, `src/rosy_bringup`, `deploy/`
- Traceability matrix in Implementation Plan §11

### External

None.

<!-- MANUAL: -->
