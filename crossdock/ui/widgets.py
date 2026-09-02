"""Shared NiceGUI widgets: info popover, row-selection column, enlarge overlay."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from typing import Any

from nicegui import ui

_notify_cache: dict[str, tuple[float, str]] = {}


def grid_default_col_def(*, sortable: bool = True, resizable: bool = False) -> dict[str, Any]:
    """Locked column headers for operational grids (no drag/hide)."""
    return {
        "sortable": sortable,
        "resizable": resizable,
        "suppressMovable": True,
        "suppressHeaderMenuButton": True,
        "lockVisible": True,
    }


def notify_once(key: str, message: str, *, type: str = "info", ttl_s: float = 3.0) -> None:
    """Show a toast at most once per key+message within ttl_s seconds."""
    now = time.monotonic()
    prev = _notify_cache.get(key)
    if prev is not None and now - prev[0] < ttl_s and prev[1] == message:
        return
    _notify_cache[key] = (now, message)
    ui.notify(message, type=type)


def notify_route_batch_results(
    *,
    dedupe_key: str,
    failures: Sequence[str],
    failure_title: str,
    success_message: str | None = None,
    partial_title: str | None = None,
) -> None:
    """One summary toast for batch route actions instead of per-row notifications."""
    if failures and success_message is None:
        body = _format_batch_lines(failures)
        notify_once(dedupe_key, f"{failure_title}:\n{body}", type="negative")
        return
    if success_message:
        ui.notify(success_message, type="positive")
    if failures:
        title = partial_title or failure_title
        body = _format_batch_lines(failures, limit=3)
        notify_once(f"{dedupe_key}:partial", f"{title}:\n{body}", type="warning")


def _format_batch_lines(items: Sequence[str], *, limit: int = 5) -> str:
    shown = items[:limit]
    lines = "\n".join(f"• {item}" for item in shown)
    if len(items) > limit:
        lines += f"\n… i {len(items) - limit} więcej"
    return lines


def reset_notify_cache_for_tests() -> None:
    """Clear dedupe cache (unit tests only)."""
    _notify_cache.clear()


def selection_column(*, multiple: bool) -> dict[str, Any]:
    """Narrow pinned checkbox column — canonical way to select grid rows."""
    column: dict[str, Any] = {
        "headerName": "",
        "colId": "_select",
        "checkboxSelection": True,
        "width": 48,
        "minWidth": 44,
        "maxWidth": 52,
        "pinned": "left",
        "lockPosition": True,
        "sortable": False,
        "filter": False,
        "resizable": False,
        "suppressMenu": True,
        "suppressMovable": True,
    }
    if multiple:
        column["headerCheckboxSelection"] = True
    return column


def info_hint(text: str, *, aria_label: str = "Co to jest?") -> None:
    """Small 'i' control; click toggles a popover with the explanation."""
    with (
        ui.button(icon="info")
        .props(f'flat round dense size=sm unelevated aria-label="{aria_label}"')
        .classes("cd-info-btn"),
        ui.menu().classes("cd-info-menu").props("auto-close"),
    ):
        ui.label(text).classes("cd-info-text")


def attach_element_enlarge(
    element: ui.element,
    compact_host: ui.element,
    *,
    title: str,
    compact_style: str,
    enlarge_style: str,
    toolbar_builder: Callable[[], None] | None = None,
    on_opened: Callable[[], None] | None = None,
    on_restored: Callable[[], None] | None = None,
) -> Callable[[], None]:
    """Move any element into a centered overlay; restore on close / Escape."""
    dialog = ui.dialog().classes("cd-enlarge-dialog")
    with dialog, ui.card().classes("cd-enlarge-card"):
        with ui.row().classes("cd-enlarge-head w-full items-center justify-between"):
            ui.label(title).classes("cd-enlarge-title")
            ui.button("Zamknij", icon="close", on_click=dialog.close).props("flat no-caps")
        if toolbar_builder is not None:
            with ui.row().classes("cd-toolbar w-full"):
                toolbar_builder()
        enlarge_host = ui.element("div").classes("cd-enlarge-host")

    def restore() -> None:
        parent = element.parent_slot.parent if element.parent_slot is not None else None
        if parent is enlarge_host:
            element.move(compact_host)
        element.style(compact_style)
        if on_restored is not None:
            on_restored()

    def open_enlarge() -> None:
        element.move(enlarge_host)
        element.style(enlarge_style)
        dialog.open()
        if on_opened is not None:
            on_opened()

    dialog.on("hide", lambda *_args: restore())
    return open_enlarge


def attach_grid_enlarge(
    grid: ui.aggrid,
    compact_host: ui.element,
    *,
    title: str,
    compact_height: str,
    toolbar_builder: Callable[[], None] | None = None,
) -> Callable[[], None]:
    """Move the same grid into a centered overlay; restore on close / Escape."""
    enlarge_height = "calc(85vh - 7.5rem)" if toolbar_builder is not None else "calc(85vh - 4.5rem)"
    return attach_element_enlarge(
        grid,
        compact_host,
        title=title,
        compact_style=f"height: {compact_height}; width: 100%",
        enlarge_style=f"height: {enlarge_height}; width: 100%",
        toolbar_builder=toolbar_builder,
    )


def enlarge_grid_button(
    grid: ui.aggrid,
    compact_host: ui.element,
    *,
    title: str,
    compact_height: str,
) -> None:
    """Toolbar control that opens the same grid in the enlarge overlay."""
    ui.button("Powiększ", icon="open_in_full").props("flat dense no-caps").on_click(
        attach_grid_enlarge(
            grid,
            compact_host,
            title=title,
            compact_height=compact_height,
        )
    )
