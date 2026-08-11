"""Tests for SQLite backup service."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from pydantic import SecretStr

from crossdock.config import Settings
from crossdock.services.backup import latest_backup, run_backup


def _settings(tmp_path: Path) -> Settings:
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO t DEFAULT VALUES")
    conn.commit()
    conn.close()
    return Settings(
        storage_secret=SecretStr("test-secret-not-for-production"),
        db_path=db,
        backup_dir=tmp_path / "backups",
        backup_keep=2,
    )


def test_run_backup_creates_openable_file(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    result = run_backup(settings)
    assert result.path.is_file()
    assert result.size_bytes > 0
    conn = sqlite3.connect(str(result.path))
    try:
        row = conn.execute("SELECT COUNT(*) FROM t").fetchone()
        assert row is not None
        assert row[0] == 1
    finally:
        conn.close()
    latest = latest_backup(settings)
    assert latest is not None
    assert latest.path == result.path


def test_backup_retention(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    for _ in range(4):
        run_backup(settings)
    files = list((tmp_path / "backups").glob("crossdock_*.db"))
    assert len(files) <= 2
