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
