"""Tests for SQLite backup service."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from pydantic import SecretStr

from crossdock.config import Settings
from crossdock.services.backup import (
    latest_backup,
    list_backups,
    resolve_backup_path,
    restore_backup,
    run_backup,
)


def _settings(tmp_path: Path, *, backup_keep: int = 5) -> Settings:
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, note TEXT)")
    conn.execute("INSERT INTO t (note) VALUES ('live')")
    conn.commit()
    conn.close()
    return Settings(
        storage_secret=SecretStr("test-secret-not-for-production"),
        db_path=db,
        backup_dir=tmp_path / "backups",
        backup_keep=backup_keep,
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
    settings = _settings(tmp_path, backup_keep=2)
    for _ in range(4):
        run_backup(settings)
    files = list((tmp_path / "backups").glob("crossdock_*.db"))
    assert len(files) <= 2


def test_list_and_restore_backup(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    first = run_backup(settings)

    conn = sqlite3.connect(str(settings.db_path))
    conn.execute("UPDATE t SET note = 'changed'")
    conn.commit()
    conn.close()

    items = list_backups(settings)
    assert items
    assert items[0].path.name == first.path.name

    restored = restore_backup(first.path.name, settings=settings, create_safety_backup=True)
    assert restored.restored_from.name == first.path.name
    assert restored.safety_backup is not None
    assert restored.safety_backup.is_file()

    conn = sqlite3.connect(str(settings.db_path))
    try:
        note = conn.execute("SELECT note FROM t").fetchone()
        assert note is not None
        assert note[0] == "live"
    finally:
        conn.close()


def test_resolve_backup_rejects_path_traversal(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    run_backup(settings)
    with pytest.raises(ValueError):
        resolve_backup_path("../crossdock_evil.db", settings)
    with pytest.raises(ValueError):
        resolve_backup_path("other.db", settings)
