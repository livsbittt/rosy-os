<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# plan

> **Status:** Historical planning area. The current Rosy OS implementation and
> Device execution source of truth is under `docs/plans/`; this directory keeps
> the upstream WBS and Flask parity evidence for traceability only.

## Purpose

Historical WBS and Flask-parity evidence. Dated working plans live in
`docs/plans/`, not here.

## Key Files

| File | Description |
|------|-------------|
| `ROSY Implementation Plan.md` | ROSY-PLN-001 v2.0 — phases P0–P6, Pn-xx tasks, AT/FAT/MAT matrix |
| `ROSY Flask Parity Checklist.md` | D-3 / P0-7 — features the old Flask nav server must still cover via FastAPI |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- Do not add new implementation tasks here. Update the dated Rosy OS plan in
  `docs/plans/` instead.

- Phases: P0 rename/multi-robot → P1 rosy_core → P2 rosy_web → P3 two-robot → P4 rosy_fleet → P5 formation → P6 expand.
- Task IDs look like `P1-9`. Prefer updating the matrix when you finish work.
- The legacy Flask UI (`src/rosy_navigation/scripts/`) was deleted; `rosy_core` FastAPI `/api/v1/*` is the only web surface (D-3).

### Testing Requirements

Parity is checked by `src/rosy_core/test/test_api.py` plus the checklist, not by running Flask.

### Common Patterns

Traceability is requirement ID → Pn-xx → test name.

## Dependencies

### Internal

- Specs in `docs/spec/`, ADRs in `docs/reference/`
- Baseline zip in `reference/src/`

### External

None.

<!-- MANUAL: -->
