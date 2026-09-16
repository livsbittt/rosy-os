"""Run each harness module's D-73 functional surface in isolation.

Usage (from Rosy OS repo root):

    python tools/harness/run_functional.py
    python tools/harness/run_functional.py --module rosy_core
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = Path(__file__).resolve().parent / "harness.yaml"


def load_modules() -> list[dict]:
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    return list(data["modules"])


def pythonpath_for(module: dict) -> str:
    extra = [str(ROOT / "src" / "rosy_core"), str(ROOT / module["path"]), str(ROOT / "test")]
    existing = os.environ.get("PYTHONPATH", "")
    parts = extra + ([existing] if existing else [])
    return os.pathsep.join(parts)


def pytest_args(module: dict) -> list[str]:
    paths = [str(ROOT / item) for item in (module.get("functional") or [])]
    return [sys.executable, "-m", "pytest", *paths, "-q", "--tb=line"]


def run_module(module: dict) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = pythonpath_for(module)
    return subprocess.run(
        pytest_args(module),
        cwd=str(ROOT),
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", action="append", dest="only")
    args = parser.parse_args()
    modules = load_modules()
    if args.only:
        wanted = set(args.only)
        modules = [item for item in modules if item["name"] in wanted]
        missing = wanted - {item["name"] for item in modules}
        if missing:
            print("unknown module:", ", ".join(sorted(missing)), file=sys.stderr)
            return 2
    failed = 0
    for module in modules:
        name = module["name"]
        proc = run_module(module)
        status = "PASS" if proc.returncode == 0 else "FAIL"
        if proc.returncode != 0:
            failed += 1
        summary = (proc.stdout or proc.stderr).strip().splitlines()
        last = summary[-1] if summary else f"exit {proc.returncode}"
        print(f"{status:4} {name:20} {last}")
        if proc.returncode != 0:
            sys.stdout.write(proc.stdout or "")
            sys.stderr.write(proc.stderr or "")
    print(f"{len(modules) - failed}/{len(modules)} modules passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
