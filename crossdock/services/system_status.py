"""System status metrics for the /system page."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from crossdock.config import Settings, get_settings
from crossdock.services.backup import latest_backup
from crossdock.storage.repositories import AssignmentRepository, OrderRepository


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
        log_tail=_log_tail(Path("data/logs"), limit=30),
    )


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
    if not log_dir.is_dir():
        return ()
    files = sorted(log_dir.glob("crossdock_*.log"), key=lambda p: p.stat().st_mtime)
    if not files:
        return ()
    try:
        lines = files[-1].read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ()
    return tuple(lines[-limit:])
