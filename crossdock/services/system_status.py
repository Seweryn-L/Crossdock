"""System status metrics for the /system page."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from crossdock.config import Settings, get_settings
from crossdock.services.backup import latest_backup
from crossdock.storage.repositories import AssignmentRepository, OrderRepository

LOG_DIR = Path("data/logs")
LOG_NAME_RE = re.compile(r"^crossdock_[A-Za-z0-9._-]+\.log$")
LOG_TAIL_LINES = 30
LOG_PREVIEW_LINES = 2000
LOG_PREVIEW_BYTES = 256 * 1024
LOG_FULL_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class SystemStatus:
    db_path: str
    db_size_bytes: int
    wal_mode: bool
    order_count: int
    disk_free_bytes: int
    disk_total_bytes: int
    latest_plan_id: int | None
    latest_plan_status: str | None
    latest_plan_wall_time_s: float | None
    last_import_summary: str | None
    last_backup_path: str | None
    last_backup_mtime: str | None
    last_backup_size_bytes: int | None
    log_tail: tuple[str, ...]
    log_files: tuple[str, ...]


@dataclass(frozen=True)
class LogFileView:
    filename: str
    lines: tuple[str, ...]
    truncated: bool
    bytes_read: int
    file_size: int


def collect_system_status(session: Session, settings: Settings | None = None) -> SystemStatus:
    settings = settings or get_settings()
    db_path = Path(settings.db_path)
    db_size = db_path.stat().st_size if db_path.is_file() else 0

    wal_mode = False
    try:
        mode = session.connection().exec_driver_sql("PRAGMA journal_mode").scalar()
        wal_mode = str(mode).lower() == "wal"
    except Exception:
        wal_mode = False

    usage = shutil.disk_usage(db_path.parent if db_path.parent.exists() else Path("."))
    run = AssignmentRepository(session).get_latest_run()
    last_import = _last_import_from_audit(session)
    backup = latest_backup(settings)
    backup_mtime = None
    if backup is not None and backup.path.is_file():
        backup_mtime = datetime.fromtimestamp(backup.path.stat().st_mtime).isoformat(
            timespec="seconds"
        )
    log_files = list_log_filenames(LOG_DIR)

    return SystemStatus(
        db_path=str(db_path.resolve()),
        db_size_bytes=db_size,
        wal_mode=wal_mode,
        order_count=OrderRepository(session).count(),
        disk_free_bytes=usage.free,
        disk_total_bytes=usage.total,
        latest_plan_id=run.id if run else None,
        latest_plan_status=run.plan_status if run else None,
        latest_plan_wall_time_s=run.wall_time_s if run else None,
        last_import_summary=last_import,
        last_backup_path=str(backup.path) if backup else None,
        last_backup_mtime=backup_mtime,
        last_backup_size_bytes=backup.size_bytes if backup else None,
        log_tail=_log_tail(LOG_DIR, limit=LOG_TAIL_LINES),
        log_files=log_files,
    )


def list_log_filenames(log_dir: Path | None = None) -> tuple[str, ...]:
    directory = log_dir or LOG_DIR
    if not directory.is_dir():
        return ()
    files = [
        path
        for path in directory.glob("crossdock_*.log")
        if path.is_file() and LOG_NAME_RE.fullmatch(path.name)
    ]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return tuple(path.name for path in files)


def read_log_file(
    filename: str,
    *,
    log_dir: Path | None = None,
    max_bytes: int = LOG_PREVIEW_BYTES,
    max_lines: int = LOG_PREVIEW_LINES,
) -> LogFileView:
    directory = (log_dir or LOG_DIR).resolve()
    safe_name = _safe_log_filename(filename)
    path = (directory / safe_name).resolve()
    if not path.is_relative_to(directory) or not path.is_file():
        raise ValueError("Nieprawidłowy plik logu.")
    cap = min(max(1, max_bytes), LOG_FULL_BYTES)
    lines, truncated, bytes_read = _read_tail_text(path, max_bytes=cap, max_lines=max_lines)
    return LogFileView(
        filename=safe_name,
        lines=lines,
        truncated=truncated,
        bytes_read=bytes_read,
        file_size=path.stat().st_size,
    )


def _safe_log_filename(filename: str) -> str:
    name = Path(filename).name
    if name != filename or ".." in filename or "/" in filename or "\\" in filename:
        raise ValueError("Nieprawidłowa nazwa pliku logu.")
    if not LOG_NAME_RE.fullmatch(name):
        raise ValueError("Nieprawidłowa nazwa pliku logu.")
    return name


def _last_import_from_audit(session: Session) -> str | None:
    try:
        rows = session.execute(
            text(
                "SELECT action, details, timestamp FROM audit_log "
                "WHERE action = 'orders.import' "
                "ORDER BY id DESC LIMIT 1"
            )
        ).first()
    except Exception:
        return None
    if rows is None:
        return None
    action, details_json, created_at = rows
    detail = ""
    if details_json:
        try:
            parsed = json.loads(details_json)
            detail = (
                f"przyjęto={parsed.get('accepted_count', parsed.get('accepted', '?'))} "
                f"odrzucono={parsed.get('rejected_count', parsed.get('rejected', '?'))}"
            )
        except Exception:
            detail = str(details_json)[:120]
    return f"{created_at} · {action} {detail}".strip()


def _log_tail(log_dir: Path, *, limit: int) -> tuple[str, ...]:
    files = list_log_filenames(log_dir)
    if not files:
        return ()
    try:
        view = read_log_file(files[0], log_dir=log_dir, max_bytes=512_000, max_lines=limit)
    except (OSError, ValueError):
        return ()
    return view.lines


def _read_tail_text(
    path: Path, *, max_bytes: int, max_lines: int
) -> tuple[tuple[str, ...], bool, int]:
    size = path.stat().st_size
    truncated = size > max_bytes
    with path.open("rb") as handle:
        if truncated:
            handle.seek(size - max_bytes)
            data = handle.read()
            newline = data.find(b"\n")
            if newline != -1:
                data = data[newline + 1 :]
        else:
            data = handle.read()
    bytes_read = len(data)
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines()
    if len(lines) > max_lines:
        truncated = True
        lines = lines[-max_lines:]
    return tuple(lines), truncated, bytes_read
