"""D-62: CORE is required; other slices are opt-in presets."""

import ast
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from robot_contracts import DEPLOY, ROOT, board_caps

CORE = ROOT / "src" / "rosy_core" / "rosy_core"
FORBIDDEN = ("rosy_omx_adapter", "rosy_control.camera", "moveit")


def board():
    return yaml.safe_load((DEPLOY / "config" / "board.yaml").read_text(encoding="utf-8"))


def test_core_is_the_only_required_slice():
    data = board()
    assert data["slices"]["required"] == ["core"]
    available = set(data["slices"]["available"])
    assert available >= {"motor", "io", "nav", "vision", "omx", "ai"}
    assert "core" not in available


def test_presets_match_current_runtime_modes():
    presets = board()["presets"]
    assert presets["core"] == ["core"]
    assert presets["motor"] == ["core", "motor"]
    assert presets["hardware"] == ["core", "motor", "io", "nav"]
    for extra in ("vision", "omx", "ai"):
        assert extra not in presets["core"]
        assert extra not in presets["motor"]
        assert extra not in presets["hardware"]


def test_core_capabilities_do_not_advertise_optional_slices():
    caps = board_caps("core")
    assert caps["navigation"]["goal_navigation"] is False
    assert caps["swarm"]["follow"] is False
    vision = caps.get("vision") or {}
    omx = caps.get("omx") or {}
    ai = caps.get("ai") or {}
    assert vision.get("enabled", False) is False
    assert omx.get("enabled", False) is False
    assert ai.get("enabled", False) is False


def test_core_package_does_not_import_optional_slice_code():
    for path in CORE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)
        for name in names:
            for banned in FORBIDDEN:
                assert name != banned and not name.startswith(banned + "."), f"{path.name} imports {name}"


def _find_usable_bash():
    candidates = []
    if os.name == "nt":
        candidates.extend(
            (
                r"C:\Program Files\Git\bin\bash.exe",
                r"C:\Program Files\Git\usr\bin\bash.exe",
            )
        )
    which = shutil.which("bash")
    if which:
        candidates.append(which)
    seen = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        if os.name == "nt" and not Path(candidate).is_file():
            continue
        try:
            probe = subprocess.run(
                [candidate, "-c", "true"],
                capture_output=True,
                timeout=2,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if probe.returncode == 0:
            return candidate
    return None


BASH = _find_usable_bash()
bash_only = pytest.mark.skipif(
    BASH is None,
    reason="bash required to source resolve-mode.sh",
)

RESOLVE_MODE = DEPLOY / "config" / "resolve-mode.sh"
INSTALLER = DEPLOY / "install-pi.sh"


def _resolve_slices(spec: str) -> subprocess.CompletedProcess:
    """Source the real resolver beside board.yaml.

    Windows drive paths are not something WSL/Git Bash can `source`; the
    runtime wrapper also loads resolve-mode.sh from this directory.
    """
    return subprocess.run(
        [
            BASH,
            "-c",
            f'source ./resolve-mode.sh; resolve_slices_to_mode "{spec}" ./board.yaml',
        ],
        cwd=str(RESOLVE_MODE.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


@bash_only
def test_slices_core_motor_resolve_to_motor_mode():
    result = _resolve_slices("core,motor")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "motor"


@bash_only
def test_slices_motor_core_order_does_not_matter():
    result = _resolve_slices("motor,core")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "motor"


@bash_only
def test_slices_core_resolves_to_core_mode():
    result = _resolve_slices("core")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "core"


@bash_only
def test_slices_core_motor_io_nav_resolve_to_hardware_mode():
    result = _resolve_slices("nav,io,motor,core")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "hardware"


@bash_only
def test_slices_missing_core_fail():
    result = _resolve_slices("motor")
    assert result.returncode != 0
    assert result.stdout.strip() == ""
    assert "core" in result.stderr.lower()


@bash_only
def test_slices_core_omx_fail_as_not_installable():
    result = _resolve_slices("core,omx")
    assert result.returncode != 0
    assert result.stdout.strip() == ""
    err = result.stderr.lower()
    assert "slice not installable yet" in err or "unknown slice" in err


@bash_only
def test_slices_unknown_name_is_refused():
    result = _resolve_slices("core,not-a-slice")
    assert result.returncode != 0
    assert result.stdout.strip() == ""
    err = result.stderr.lower()
    assert "slice not installable yet" in err or "unknown slice" in err


def test_installer_accepts_preset_and_slices_mutually_exclusive():
    text = INSTALLER.read_text(encoding="utf-8")
    assert "--preset" in text
    assert "--slices" in text
    assert "mutually exclusive" in text
    assert "resolve_slices_to_mode" in text
    assert "resolve_runtime_mode" in text
    assert "INSTALL_RUNTIME_MODE" in text

    env_fn = text[
        text.index("write_runtime_environment() {") : text.index("build_and_start_core() {")
    ]
    assert "INSTALL_RUNTIME_MODE" in env_fn
    assert 'set_env_value "$env_file" ROSY_RUNTIME_MODE core' not in env_fn

    start_fn = text[
        text.index("build_and_start_core() {") : text.index("enable_boot_service() {")
    ]
    assert 'ROSY_RUNTIME_MODE=core "$runtime_dir/runtime-mode.sh" down' in start_fn
    assert 'ROSY_RUNTIME_MODE=core "$runtime_dir/runtime-mode.sh" up' in start_fn

    main = text[text.index("main() {"):]
    assert "parse_install_cli" in main
    assert main.index("parse_install_cli") < main.index("write_runtime_environment")
