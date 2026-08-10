"""Application configuration loaded from environment / .env file.

Business thresholds (e.g. default delivery days, FR-024) live here,
not in code, per project convention.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_path}"


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except Exception as exc:
        raise RuntimeError(
            "Brak poprawnej konfiguracji. Skopiuj .env.example do .env i uzupełnij "
            "wartości (w szczególności CROSSDOCK_STORAGE_SECRET)."
        ) from exc
