"""Tests for system status log listing and safe file reads."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from crossdock.services.system_status import list_log_filenames, read_log_file


def test_list_log_filenames_newest_first(tmp_path: Path) -> None:
    older = tmp_path / "crossdock_2026-08-01.log"
    newer = tmp_path / "crossdock_2026-08-16.log"
    older.write_text("old\n", encoding="utf-8")
    newer.write_text("new\n", encoding="utf-8")
    os.utime(older, (1_700_000_000, 1_700_000_000))
    os.utime(newer, (1_800_000_000, 1_800_000_000))
    names = list_log_filenames(tmp_path)
    assert names == ("crossdock_2026-08-16.log", "crossdock_2026-08-01.log")


def test_list_log_filenames_empty_dir(tmp_path: Path) -> None:
    assert list_log_filenames(tmp_path) == ()


def test_read_log_file_returns_tail_and_rejects_traversal(tmp_path: Path) -> None:
    path = tmp_path / "crossdock_2026-08-16.log"
    path.write_text("\n".join(f"line-{i}" for i in range(30)), encoding="utf-8")
    view = read_log_file("crossdock_2026-08-16.log", log_dir=tmp_path, max_lines=10)
    assert view.filename == "crossdock_2026-08-16.log"
    assert view.lines[-1] == "line-29"
    assert len(view.lines) == 10

    with pytest.raises(ValueError, match="Nieprawidłow"):
        read_log_file("../crossdock_2026-08-16.log", log_dir=tmp_path)
    with pytest.raises(ValueError, match="Nieprawidłow"):
        read_log_file("secret.txt", log_dir=tmp_path)
