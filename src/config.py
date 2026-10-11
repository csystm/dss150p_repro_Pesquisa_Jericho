"""Load the reproduction policy from config/settings.yml.

Precedence at runtime (highest wins): CLI argument > environment variable >
this file. This module only exposes the YAML values; callers apply overrides.

Usage:
    from src.config import get, settings
    seed = get("run.seed")
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "settings.yml"


@lru_cache(maxsize=1)
def settings() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"settings file missing: {CONFIG_PATH}")
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def get(dotted_key: str, default: Any = None) -> Any:
    """Dotted-path getter. Example: get('split.test_size') -> 0.2"""
    node: Any = settings()
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def reload() -> None:
    """Clear the cache; used by tests."""
    settings.cache_clear()