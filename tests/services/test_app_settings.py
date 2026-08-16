"""Tests for runtime settings overlay."""

from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr

from crossdock.config import Settings, get_settings
from crossdock.services import app_settings
from crossdock.services.app_settings import (
    editable_settings_snapshot,
    load_runtime_overrides,
    save_runtime_overrides,
)


def test_save_and_load_runtime_overrides(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "runtime_settings.json"
    monkeypatch.setenv("CROSSDOCK_STORAGE_SECRET", "test-secret-not-for-production")
    get_settings.cache_clear()

    save_runtime_overrides(
        {"max_drops_per_route": 5, "cost_per_km": 2.5},
        path=path,
    )
    assert load_runtime_overrides(path)["max_drops_per_route"] == 5

    base = Settings(storage_secret=SecretStr("test-secret-not-for-production"))
    data = base.model_dump()
    data.update(load_runtime_overrides(path))
    merged = Settings.model_validate(data)
    assert merged.max_drops_per_route == 5
    assert merged.cost_per_km == 2.5

    snap = editable_settings_snapshot(merged)
    assert "max_drops_per_route" in snap
    assert "default_kg_per_pallet" in snap
    assert "kg_per_pallet_bus" in snap
    assert "storage_secret" not in snap
    assert "host" not in snap
    assert "admin_password" not in snap


def test_get_settings_reads_runtime_overlay(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "runtime_settings.json"
    monkeypatch.setenv("CROSSDOCK_STORAGE_SECRET", "test-secret-not-for-production")
    monkeypatch.setattr(app_settings, "RUNTIME_SETTINGS_PATH", path)
    get_settings.cache_clear()

    save_runtime_overrides(
        {"max_drops_per_route": 7, "solver_seed": 99},
        path=path,
    )
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.max_drops_per_route == 7
    assert settings.solver_seed == 99

    # Secrets / server bind stay out of editable overlay
    snap = editable_settings_snapshot(settings)
    assert "storage_secret" not in snap
    assert "port" not in snap
