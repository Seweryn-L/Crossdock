"""Shared NiceGUI widgets: info popover, row-selection column, enlarge overlay."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from nicegui import ui


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


def attach_grid_enlarge(
    grid: ui.aggrid,
    compact_host: ui.element,
    *,
    title: str,
    compact_height: str,
    toolbar_builder: Callable[[], None] | None = None,
) -> Callable[[], None]:
    """Move the same grid into a centered overlay; restore on close / Escape."""
    dialog = ui.dialog().classes("cd-enlarge-dialog")
    with dialog, ui.card().classes("cd-enlarge-card"):
        with ui.row().classes("cd-enlarge-head w-full items-center justify-between"):
            ui.label(title).classes("cd-enlarge-title")
            ui.button("Zamknij", icon="close", on_click=dialog.close).props("flat no-caps")
        if toolbar_builder is not None:
            with ui.row().classes("cd-toolbar w-full"):
                toolbar_builder()
        enlarge_host = ui.element("div").classes("cd-enlarge-host")

    enlarge_height = "calc(85vh - 7.5rem)" if toolbar_builder is not None else "calc(85vh - 4.5rem)"

    def restore() -> None:
        parent = grid.parent_slot.parent if grid.parent_slot is not None else None
        if parent is enlarge_host:
            grid.move(compact_host)
        grid.style(f"height: {compact_height}; width: 100%")

    def open_enlarge() -> None:
        grid.move(enlarge_host)
        grid.style(f"height: {enlarge_height}; width: 100%")
        dialog.open()

    dialog.on("hide", lambda *_args: restore())
    return open_enlarge


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
