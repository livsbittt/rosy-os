"""rosy_core.config — YAML 설정 로드/검증 (P1-1, CFG-001/002).

설정 계층:
1. config/rosy_default.yaml (패키지 기본값)
2. ~/.rosy/rosy.yaml (로봇 로컬 오버라이드) — 있으면 병합
3. 환경변수 ROSY_CONFIG (명시적 경로) — 최우선
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import yaml

DEFAULT_CONFIG_NAME = "rosy_default.yaml"
LOCAL_CONFIG_PATH = Path.home() / ".rosy" / "rosy.yaml"


def _deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _find_default_config() -> Path:
    try:
        from ament_index_python.packages import get_package_share_directory

        share = Path(get_package_share_directory("rosy_core")) / "config"
        if (share / DEFAULT_CONFIG_NAME).exists():
            return share / DEFAULT_CONFIG_NAME
    except Exception:
        pass
    # 소스 트리 실행 (colcon install 미사용) 폴백
    return Path(__file__).resolve().parent.parent / "config" / DEFAULT_CONFIG_NAME


def load_config(explicit_path: Optional[str] = None) -> dict[str, Any]:
    """기본값 → 로컬 오버라이드 → 명시적 경로 순으로 병합해 반환한다."""

    base_path = Path(explicit_path) if explicit_path else _find_default_config()
    config: dict[str, Any] = {}
    with open(base_path, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    override_path = Path(os.environ.get("ROSY_CONFIG", "")) if os.environ.get("ROSY_CONFIG") else LOCAL_CONFIG_PATH
    if override_path.exists():
        with open(override_path, encoding="utf-8") as f:
            config = _deep_merge(config, yaml.safe_load(f) or {})

    namespace = os.environ.get("ROSY_NAMESPACE", "").strip().strip("/")
    if namespace:
        config.setdefault("robot", {})["frame_prefix"] = f"{namespace}/"

    return config
