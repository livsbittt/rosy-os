# Pinky operator validation design

Date: 2026-09-21
Status: Implemented locally
Scope: stationary Windows-to-Pinky preflight only

## Objective

Give the operator one copyable command that answers whether the connected
Pinky has the intended signed release, identity, CORE runtime, ROS graph, API,
and dashboard. The result must be durable evidence and must never authorize or
cause motion.

## Options considered

1. Keep only the long G0-G5 runbook. This remains authoritative but is too easy
   to execute partially during first connection.
2. Put commissioning actions in the dashboard. This would mix observation with
   privileged host and motor actions before device trust is established.
3. Add a read-only Windows collector that hands off to the existing G3-G5
   runbook. This reuses the current trust boundary and keeps physical actions
   behind explicit gates.

Option 3 is selected.

## Components and data flow

`validate-pinky-from-windows.ps1` calls the existing peer verifier, then runs
the installed secret-free `device-readback.sh --json` through bounded key-based
SSH. `pinky_validation.py` compares the readback with the operator-supplied
robot number and full signed-manifest revision. It emits one summary with
`GO` or `HOLD`, named failed checks, the verified dashboard URL, and a fixed
`motion_authorized: false` value. SHA-256 hashes bind the collected files.

The collector performs no install, release activation, runtime-mode change,
calibration, motor probe, or motion command. A stationary `GO` advances only to
`G3_SENSOR_ONLY`; G4 and G5 retain their physical safeguards.

## Failure handling

Inputs are validated before SSH. Evidence directories and files are never
overwritten. Connection or readback failure produces a `HOLD` summary when
connection evidence exists. Missing non-interactive privilege does not invite
credential entry or weaken the gate; the operator switches to the documented
local-console path. Expected identity, revision, core-only quarantine, or field
scope mismatch all fail closed.

## Acceptance

- Unit evidence proves exact identity/revision checks and permanent motion hold.
- A PowerShell failure-path test proves an unreachable device leaves actionable
  `HOLD` evidence.
- A full PowerShell test with fake SSH and a loopback HTTP peer proves the
  successful collector path and evidence hashes without a robot.
- A real Pinky remains required to move DEVICE from `HOLD` to `GO`; local tests
  and Gazebo do not satisfy that gate.
