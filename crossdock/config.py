"""Application configuration loaded from environment / .env file.

Business thresholds (e.g. default delivery days, FR-024) live here,
not in code, per project convention.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Keys editable from Ustawienia → Parametry (runtime JSON overlay).
EDITABLE_SETTING_KEYS: frozenset[str] = frozenset(
    {
        "depot_latitude",
        "depot_longitude",
        "min_fill_ratio",
        "max_drops_per_route",
        "solver_time_limit_s",
        "solver_seed",
        "default_delivery_days",
        "cost_per_km",
        "storage_cost_per_pallet_day",
        "ltl_cost_multiplier",
        "buffer_savings_threshold",
        "max_buffer_days",
        "planning_date",
        "ship_lead_days",
        "warehouse_capacity_kg",
        "upload_max_mb",
        "backup_keep",
        "backup_hour",
        "backup_minute",
    }
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CROSSDOCK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    storage_secret: SecretStr
    admin_password: SecretStr | None = None
    db_path: Path = Path("data/crossdock.db")
    host: str = "0.0.0.0"
    port: int = 8080
    session_max_idle_minutes: int = 60
    default_delivery_days: int = 7
    # Excel column mapping — placeholder until Sandra's dictionary (W-02).
    excel_mapping_path: Path = Path("config/excel_column_mapping.json")
    upload_max_mb: int = 20
    # Cross-dock depot approx. Herentals / ~30 km from Antwerp (MVP seed).
    depot_latitude: float = 51.176
    depot_longitude: float = 4.836
    # Business thresholds (proposals from SRS §9.2 — keep in config, not code).
    min_fill_ratio: float = 0.90
    max_drops_per_route: int = 3
    # CP-SAT assignment (T3) — hard time limit + seed for reproducibility.
    solver_time_limit_s: float = 45.0
    solver_seed: int = 42
    # Placeholder freight rate until Sandra's rates (W-06); used for plan cost display.
    cost_per_km: float = 1.2
    # FR-022 buffering placeholders (W-06) — replace after Sandra's rates.
    buffer_savings_threshold: float = 0.15
    storage_cost_per_pallet_day: float = 2.0
    ltl_cost_multiplier: float = 1.8
    max_buffer_days: int = 3
    # Simulation clock: None = real calendar today. Used as "day T" for SLA.
    planning_date: date | None = None
    # Days before delivery_date that the order must leave the warehouse.
    ship_lead_days: int = 2
    # Cross-dock holding capacity for occupancy monitoring (kg placeholder).
    warehouse_capacity_kg: float = 50000.0
    backup_dir: Path = Path("data/backups")
    backup_keep: int = 14
    backup_hour: int = 2
    backup_minute: int = 30

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_path}"


def _apply_runtime_overrides(settings: Settings) -> Settings:
    """Overlay data/runtime_settings.json onto env-loaded settings."""
    from crossdock.services.app_settings import load_runtime_overrides

    overrides = load_runtime_overrides()
    if not overrides:
        return settings
    data: dict[str, Any] = settings.model_dump()
    for key, value in overrides.items():
        if key in EDITABLE_SETTING_KEYS:
            data[key] = value
    return Settings.model_validate(data)


@lru_cache
def get_settings() -> Settings:
    try:
        base = Settings()  # type: ignore[call-arg]
    except Exception as exc:
        raise RuntimeError(
            "Brak poprawnej konfiguracji. Skopiuj .env.example do .env i uzupełnij "
            "wartości (w szczególności CROSSDOCK_STORAGE_SECRET)."
        ) from exc
    return _apply_runtime_overrides(base)


def effective_planning_date(settings: Settings | None = None) -> date:
    """Simulation day T, or the real calendar date when unset."""
    cfg = settings if settings is not None else get_settings()
    return cfg.planning_date if cfg.planning_date is not None else date.today()
