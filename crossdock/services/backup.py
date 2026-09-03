"""SQLite online backup (stdlib sqlite3 backup API) and restore."""

from __future__ import annotations

import os
import shutil
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


@dataclass(frozen=True)
class BackupInfo:
    path: Path
    size_bytes: int
    mtime: datetime

    @property
    def label(self) -> str:
        return f"{self.mtime.strftime('%d.%m.%Y %H:%M')} · {self.path.name}"


@dataclass(frozen=True)
class RestoreResult:
    restored_from: Path
    safety_backup: Path | None
    size_bytes: int


def run_backup(settings: Settings | None = None) -> BackupResult:
    settings = settings or get_settings()
    db_path = Path(settings.db_path)
    if not db_path.is_file():
        raise FileNotFoundError(f"Brak pliku bazy: {db_path}")

    backup_dir = Path(settings.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = backup_dir / f"crossdock_{stamp}.db"
    if dest.exists():
        dest = backup_dir / f"crossdock_{stamp}_{os.getpid()}.db"

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
    items = list_backups(settings)
    if not items:
        return None
    latest = items[0]
    return BackupResult(path=latest.path, size_bytes=latest.size_bytes)


def list_backups(settings: Settings | None = None) -> list[BackupInfo]:
    """Return backups newest-first (only ``crossdock_*.db`` under backup_dir)."""
    settings = settings or get_settings()
    backup_dir = Path(settings.backup_dir).resolve()
    if not backup_dir.is_dir():
        return []
    items: list[BackupInfo] = []
    for path in backup_dir.glob("crossdock_*.db"):
        resolved = path.resolve()
        if not _is_under_dir(resolved, backup_dir):
            continue
        if not resolved.is_file():
            continue
        stat = resolved.stat()
        items.append(
            BackupInfo(
                path=resolved,
                size_bytes=stat.st_size,
                mtime=datetime.fromtimestamp(stat.st_mtime),
            )
        )
    items.sort(key=lambda b: b.mtime, reverse=True)
    return items


def resolve_backup_path(filename: str, settings: Settings | None = None) -> Path:
    """Resolve a backup filename inside backup_dir (rejects path traversal)."""
    settings = settings or get_settings()
    backup_dir = Path(settings.backup_dir).resolve()
    name = Path(filename).name
    if name != filename or not name.startswith("crossdock_") or not name.endswith(".db"):
        raise ValueError("Nieprawidłowa nazwa kopii zapasowej.")
    candidate = (backup_dir / name).resolve()
    if not _is_under_dir(candidate, backup_dir):
        raise ValueError("Ścieżka kopii poza katalogiem backupów.")
    if not candidate.is_file():
        raise FileNotFoundError(f"Brak kopii: {name}")
    return candidate


def restore_backup(
    filename: str,
    *,
    settings: Settings | None = None,
    create_safety_backup: bool = True,
) -> RestoreResult:
    """Replace live DB with a dated backup. Disposes SQLAlchemy engine connections."""
    from crossdock.storage.database import reset_engine

    settings = settings or get_settings()
    source = resolve_backup_path(filename, settings)
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Copy source aside first so a same-minute safety backup cannot overwrite it.
    staged = source.with_suffix(source.suffix + ".restore")
    shutil.copy2(source, staged)

    safety: Path | None = None
    try:
        if create_safety_backup and db_path.is_file():
            safety_result = run_backup(settings)
            safety = safety_result.path

        reset_engine()
        shutil.copy2(staged, db_path)
        reset_engine()
    finally:
        staged.unlink(missing_ok=True)

    size = db_path.stat().st_size
    logger.info("Przywrócono bazę z {} (safety={})", source, safety)
    return RestoreResult(restored_from=source, safety_backup=safety, size_bytes=size)


def _is_under_dir(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


def _prune_old_backups(backup_dir: Path, *, keep: int) -> None:
    files = sorted(backup_dir.glob("crossdock_*.db"), key=lambda p: p.stat().st_mtime)
    excess = len(files) - max(keep, 1)
    if excess <= 0:
        return
    for path in files[:excess]:
        path.unlink(missing_ok=True)
        logger.info("Usunięto stary backup {}", path)
