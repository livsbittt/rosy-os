"""`RosBridge` must implement every member the executor contracts declare.

This is the test that would have caught D-32 at its root. `NavExecutor` and
`DockingExecutor` are `typing.Protocol`s and `RosBridge` declares no base class,
so conformance is duck-typed and nothing — not the type system, not CI, not the
host suite — notices when a member is missing. `reset_mapping` was absent for
the whole life of the endpoint that called it, hidden behind a `hasattr` probe;
removing the probe removes the hiding place but not the underlying exposure. Add
a member to a Protocol, forget the bridge, call it as `self.executor.foo()`, and
you have reproduced D-32 with no `hasattr` anywhere for C6 to find.

`bridge/AGENTS.md` records why an import-based check is not available here: host
pytest cannot import `ros_bridge.py`, because rclpy is not installed on the dev
machine and is optional in the core image. So this reads the source with `ast`,
the same technique and for the same reason as `test_module_criteria.py`.

That makes it a structural check, not a behavioural one: it proves the method
exists, never that it does the right thing. `RosBridge.reset_mapping` is still
verified by nothing on either platform — it is unreachable on all three deploy
overlays, which are `slam: false`. This test closes the omission, not the gap.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1] / "rosy_core"

#: (contract module, Protocol class) -> the class expected to implement it.
CONTRACTS = [
    ("navigation/manager.py", "NavExecutor"),
    ("docking/manager.py", "DockingExecutor"),
]
IMPLEMENTER = ("bridge/ros_bridge.py", "RosBridge")


def _class_def(relative: str, name: str) -> ast.ClassDef:
    tree = ast.parse((PACKAGE / relative).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {relative}")


def _methods(node: ast.ClassDef) -> set[str]:
    return {
        member.name
        for member in node.body
        if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not member.name.startswith("_")
    }


@pytest.mark.parametrize("relative,protocol", CONTRACTS, ids=[c[1] for c in CONTRACTS])
def test_ros_bridge_implements_every_declared_contract_member(relative, protocol):
    declared = _methods(_class_def(relative, protocol))
    implemented = _methods(_class_def(*IMPLEMENTER))
    missing = declared - implemented

    assert not missing, (
        f"RosBridge does not implement {sorted(missing)}, declared by {protocol} "
        f"in {relative}.\n"
        "The Protocol is structural and RosBridge declares no base, so nothing "
        "else catches this: the call fails at runtime with AttributeError, which "
        "api/errors.py does not handle, so the endpoint answers 500 — the 일반 "
        "실패 CAP-003 forbids. Implement the member, or remove it from the "
        "contract. If the runtime genuinely cannot honour it, implement it and "
        "raise CAPABILITY_NOT_SUPPORTED, as reset_mapping does (D-32)."
    )
