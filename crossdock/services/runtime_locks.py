"""Process-local runtime locks (e.g. block restore during Generuj)."""

from __future__ import annotations

_solver_running = False


def set_solver_running(value: bool) -> None:
    global _solver_running
    _solver_running = bool(value)


def is_solver_running() -> bool:
    return _solver_running
