# Module Coupling Consistency Continuation Plan

- Date: 2026-09-21
- Status: Proposed

## Context

Following D-126 (Full Module Separation) and the extraction of cross-domain
integration scripts (`simulate_*.py`) to the repository-level `tools/`
directory, the measured static dependencies between core and control no longer
require a source-level back-edge. Maintaining that result still needs explicit
build-time and runtime guardrails; the move and this proposal are not by
themselves proof of zero coupling.

## Proposed ADRs

### 1. [ADR-1003] Zero-Coupling AST Validation (Build-time Guard)

- **Problem**: Python's dynamic nature allows accidental cross-domain imports
  that pass in a monolithic development environment but break isolated runtime
  slices.
- **Decision**: Introduce an automated AST parser in
  `test/test_module_boundaries.py`. It will inspect `import` and
  `from ... import ...` statements and reject dependencies outside the explicit
  domain allowlist. Test-only boundaries remain separately declared.

### 2. [ADR-1004] ROS 2 Namespace Strict Segregation (Runtime Guard)

- **Problem**: Static imports can be clean while ROS 2 topics remain global. An
  application node could accidentally publish the operational final
  `cmd_vel`, violating D-2.
- **Decision**: Define and test a topic-ownership allowlist. `apps/control`
  publishes evidence/sensor topics only; CORE owns operational state, intent
  and final `cmd_vel`. A launch/graph check must verify actual publishers before
  this proposal can become Accepted.

### 3. [ADR-1005] Shared Headless UI Package (Monorepo Web Decoupling)

- **Problem**: ADR-1002 puts the framework-free adapter in `core_api_web`.
  Fleet or future dashboards must not import a robot dashboard package merely
  to consume the server-judged evidence vocabulary.
- **Decision**: Evaluate extraction of `core_ui_logic.js` and frontend protocol
  types into a neutral `web_common` package. Extraction is accepted only when
  both consumers exist and package-boundary tests prove there is no visual
  component sharing or reverse dependency.
