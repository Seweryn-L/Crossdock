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
    from crossdock.services.fleet import seed_placeholder_fleet, sync_fleet_capacities_from_seed

    with session_scope() as session:
        added = seed_placeholder_fleet(session)
        synced = sync_fleet_capacities_from_seed(session)
    if added:
        logger.info(
            "Utworzono {} pojazdów floty (pojemności z FLota / W-03).",
            added,
        )
    if synced:
        logger.info(
            "Zsynchronizowano pojemności {} pojazdów ze seedem Martyny (W-03).",
            synced,
        )


def _seed_locations() -> None:
    from crossdock.services.locations import seed_location_coords

    with session_scope() as session:
        added = seed_location_coords(session)
    if added:
        logger.info("Uzupełniono słownik lokalizacji seedem ({} wpisów).", added)


def _start_backup_scheduler() -> None:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    from crossdock.services.backup import run_backup

    settings = get_settings()
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_backup,
        CronTrigger(hour=settings.backup_hour, minute=settings.backup_minute),
        id="sqlite_nightly_backup",
        replace_existing=True,
    )
    scheduler.start()
    app.on_shutdown(scheduler.shutdown)
    logger.info(
        "Zaplanowano nocny backup SQLite o {:02d}:{:02d} → {}",
        settings.backup_hour,
        settings.backup_minute,
        settings.backup_dir,
    )


def main() -> None:
    _configure_logging()
    settings = get_settings()
    _seed_admin()
    _seed_fleet()
    _seed_locations()
    _start_backup_scheduler()

    # Imports register @ui.page routes and the auth middleware.
    from crossdock.ui import login_page, pages  # noqa: F401
    from crossdock.ui.auth_middleware import AuthMiddleware
    from crossdock.ui.layout import (
        ThemeHtmlMiddleware,
        register_theme_bootstrap,
        register_ui_static,
    )

    register_ui_static()
    register_theme_bootstrap()
    app.add_middleware(ThemeHtmlMiddleware)
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
