"""Runtime dependencies required by the split CORE API package."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT.parent / "core"


def test_api_and_core_declare_their_imported_web_runtime():
    api_package = (ROOT / "package.xml").read_text(encoding="utf-8")
    core_package = (CORE / "package.xml").read_text(encoding="utf-8")

    assert "<exec_depend>python3-fastapi</exec_depend>" in api_package
    assert "<exec_depend>python3-uvicorn</exec_depend>" in core_package
