"""Application entry point: logging, admin seed, NiceGUI server."""

import sys
from pathlib import Path

from loguru import logger
from nicegui import app, ui

from crossdock.config import get_settings
from crossdock.services.auth import AuthService
from crossdock.storage.database import session_scope


def _configure_logging() -> None:
    logger.remove()
    logger.add(sys.stderr, level="INFO", enqueue=True)
    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_dir / "crossdock_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="30 days",
        level="DEBUG",
        enqueue=True,
        diagnose=True,
    )


def _seed_admin() -> None:
    settings = get_settings()
    if settings.admin_password is None:
        logger.info("CROSSDOCK_ADMIN_PASSWORD nie ustawione — pomijam seed admina.")
        return
    with session_scope() as session:
        created = AuthService(session).seed_admin(settings.admin_password.get_secret_value())
    if created:
        logger.info("Utworzono startowe konto administratora 'admin'.")


def _seed_fleet() -> None:
    from crossdock.services.fleet import seed_placeholder_fleet

    with session_scope() as session:
        added = seed_placeholder_fleet(session)
    if added:
        logger.info(
            "Utworzono {} pojazdów placeholder (PLACEHOLDER_PENDING_MARTYNA / W-03).",
            added,
        )


def main() -> None:
    _configure_logging()
    settings = get_settings()
    _seed_admin()
    _seed_fleet()

    # Imports register @ui.page routes and the auth middleware.
    from crossdock.ui import login_page, pages  # noqa: F401
    from crossdock.ui.auth_middleware import AuthMiddleware

    app.add_middleware(AuthMiddleware)

    logger.info("Start serwera Crossdock na {}:{}", settings.host, settings.port)
    ui.run(
        host=settings.host,
        port=settings.port,
        title="Crossdock",
        storage_secret=settings.storage_secret.get_secret_value(),
        favicon="🚚",
        language="pl",
        reload=False,
        show=False,
    )


# NiceGUI on Windows respawns the process via multiprocessing (spawn);
# both guards are required so `uv run crossdock` works with run.cpu_bound later.
if __name__ in {"__main__", "__mp_main__"}:
    main()
