"""SQLite online backup (stdlib sqlite3 backup API)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from loguru import logger

from crossdock.config import Settings, get_settings


@dataclass(frozen=True)
class BackupResult:
    path: Path
    size_bytes: int


def run_backup(settings: Settings | None = None) -> BackupResult:
    settings = settings or get_settings()
    db_path = Path(settings.db_path)
    if not db_path.is_file():
        raise FileNotFoundError(f"Brak pliku bazy: {db_path}")

    backup_dir = Path(settings.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    dest = backup_dir / f"crossdock_{stamp}.db"

    src = sqlite3.connect(str(db_path))
    try:
        dst = sqlite3.connect(str(dest))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

    _prune_old_backups(backup_dir, keep=settings.backup_keep)
    size = dest.stat().st_size
    logger.info("Backup SQLite → {} ({} B)", dest, size)
    return BackupResult(path=dest, size_bytes=size)


def latest_backup(settings: Settings | None = None) -> BackupResult | None:
    settings = settings or get_settings()
    backup_dir = Path(settings.backup_dir)
    if not backup_dir.is_dir():
        return None
    files = sorted(backup_dir.glob("crossdock_*.db"), key=lambda p: p.stat().st_mtime)
    if not files:
        return None
    latest = files[-1]
    return BackupResult(path=latest, size_bytes=latest.stat().st_size)


def _prune_old_backups(backup_dir: Path, *, keep: int) -> None:
    files = sorted(backup_dir.glob("crossdock_*.db"), key=lambda p: p.stat().st_mtime)
    excess = len(files) - max(keep, 1)
    if excess <= 0:
        return
    for path in files[:excess]:
        path.unlink(missing_ok=True)
        logger.info("Usunięto stary backup {}", path)
