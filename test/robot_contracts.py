"""Shared paths for host-side robot runtime contract tests."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy" / "robot"
NAV_LAUNCH = ROOT / "src" / "rosy_navigation" / "launch"
NAV_PARAMS = ROOT / "src" / "rosy_navigation" / "params" / "nav2_params.yaml"


def compose() -> dict:
    return yaml.safe_load((DEPLOY / "compose.yaml").read_text(encoding="utf-8"))


def board_caps(mode: str) -> dict:
    return yaml.safe_load(
        (DEPLOY / "config" / f"capabilities.{mode}.yaml").read_text(encoding="utf-8")
    )


def board_profile(mode: str) -> dict:
    return yaml.safe_load(
        (DEPLOY / "config" / f"profile.{mode}.yaml").read_text(encoding="utf-8")
    )
