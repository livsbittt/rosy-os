# Pinky connection evidence design

Date: 2026-09-21
Status: Accepted for implementation

## Purpose

Before G0, prove that the exact Pinky host is reachable from the operator PC,
that key-based SSH can inspect the selected Pi interface, and that the ROSY API
and dashboard answer over that interface. Preserve the result as machine-readable
evidence without changing network, runtime, motors, or robot state.

## Approach

Extend `verify-from-windows.ps1` instead of adding a second discovery path. The
operator still supplies the trusted hostname or IPv4 address. Optional batch
mode adds bounded SSH connection attempts for unattended validation. An optional
evidence path receives one atomic JSON record on both GO and HOLD outcomes.

The record contains only the target identity, selected interface and address,
HTTP endpoint status, timestamps, stable failure code, and overall outcome. It
does not contain credentials, SSH output, headers, environment variables, or
robot commands. Existing console output and interactive authentication remain
the default when the new options are omitted.

## Failure handling

Unsafe parameters, missing SSH, route/address failures, invalid IPv4, and HTTP
failures all stop the verifier. If an evidence path was requested, the failure
is written before the non-zero exit. Existing evidence is never overwritten;
the write uses a sibling temporary file and a no-replace move.

## Verification

Python tests launch PowerShell with a fake SSH executable and a loopback HTTP
server. They prove GO JSON, HOLD JSON, bounded batch SSH options, exact endpoint
checks, no overwrite, and absence of unsafe host-key bypass. Existing deployment
and commissioning tests remain the regression boundary.
