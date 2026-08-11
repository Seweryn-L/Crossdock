"""Runtime business settings overlay (JSON) on top of env Settings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from crossdock.config import EDITABLE_SETTING_KEYS, Settings, get_settings
from crossdock.storage.repositories import AuditLogRepository

RUNTIME_SETTINGS_PATH = Path("data/runtime_settings.json")


def load_runtime_overrides(path: Path | None = None) -> dict[str, Any]:
    target = path or RUNTIME_SETTINGS_PATH
    if not target.is_file():
        return {}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if k in EDITABLE_SETTING_KEYS}


def save_runtime_overrides(
    updates: dict[str, Any],
    *,
    session: Session | None = None,
    username: str = "system",
    path: Path | None = None,
) -> Settings:
    """Merge updates into runtime JSON, clear settings cache, return fresh Settings."""
    target = path or RUNTIME_SETTINGS_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    current = load_runtime_overrides(target)
    for key, value in updates.items():
        if key not in EDITABLE_SETTING_KEYS:
            continue
        current[key] = value
    target.write_text(
        json.dumps(current, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    get_settings.cache_clear()
    if session is not None:
        AuditLogRepository(session).record(
            username=username,
            action="settings.update",
            details={"keys": sorted(updates.keys())},
        )
    return get_settings()


def editable_settings_snapshot(settings: Settings | None = None) -> dict[str, Any]:
    cfg = settings or get_settings()
    out: dict[str, Any] = {}
    for key in EDITABLE_SETTING_KEYS:
        val = getattr(cfg, key)
        if isinstance(val, Path):
            out[key] = str(val)
        else:
            out[key] = val
    return out
