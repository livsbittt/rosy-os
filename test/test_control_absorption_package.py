"""Rosy Control must be owned and importable from the Rosy OS source tree."""

from __future__ import annotations

import importlib.util
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
PACKAGE = REPO / "src" / "rosy_control"


def test_control_package_is_part_of_the_os_workspace() -> None:
    assert (PACKAGE / "package.xml").is_file()
    assert (PACKAGE / "setup.py").is_file()
    assert (PACKAGE / "resource" / "rosy_control").is_file()


def test_control_package_imports_without_the_legacy_checkout() -> None:
    module = PACKAGE / "rosy_control" / "__init__.py"
    spec = importlib.util.spec_from_file_location("absorbed_rosy_control", module)
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    assert Path(loaded.__file__).resolve().is_relative_to(PACKAGE.resolve())


def test_control_tests_are_owned_by_the_os_workspace() -> None:
    tests = list((PACKAGE / "test").glob("test_*.py"))
    assert len(tests) >= 100


def test_os_source_catalog_owns_the_absorbed_package() -> None:
    catalog = (REPO / "src" / "AGENTS.md").read_text(encoding="utf-8")
    assert "`rosy_control/`" in catalog
