# 13. ROSY Current-to-Target Migration Plan

## 1. Principle

ROSY is already under implementation.

Therefore:

> Do not perform a full rewrite unless absolutely necessary.

Use incremental refactoring.

## 2. Migration Actions

Every existing module must be classified as:

- KEEP
- MOVE
- RENAME
- REFACTOR
- DEPRECATE
- REWRITE

## 3. Example Mapping

| Current Module | Target Module | Action |
|---|---|---|
| Robot Manager | rosy-device / rosy-control | Refactor |
| ROS Bridge | rosy-fabric | Move |
| Pinky Control | adapters/pinky | Refactor |
| AI Worker | rosy-compute | Move |
| Web API | rosy-api | Keep |
| Fleet Logic | rosy-control | Refactor |

## 4. Migration Phases

### Phase 0 - Freeze Architecture Terms

Finalize:

- Node
- Device
- Component
- Capability
- Asset
- Task

### Phase 1 - Introduce ROSY Base Runtime

Create:

- identity
- profiles
- lifecycle
- plugin manager
- heartbeat

### Phase 2 - Move Device-Specific Code

Move:

- Pinky code to Pinky adapter
- OMX code to OMX adapter

### Phase 3 - Introduce Capability Registry

Remove direct hardware assumptions from Task logic.

### Phase 4 - Introduce Compute Fabric

Move AI/edge execution into ROSY Compute.

### Phase 5 - Composite Asset

Create:

`Pinky + OMX = MobileManipulator`

## 5. Migration Rule

New code should follow target architecture immediately.

Existing code should be migrated only when touched or when it blocks target architecture.
