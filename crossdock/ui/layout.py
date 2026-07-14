"""Shared page frame: header, navigation drawer, logout. UI texts in Polish."""

from collections.abc import Iterator
from contextlib import contextmanager

from nicegui import app, ui

NAV_ITEMS = [
    ("Pulpit", "/", "dashboard"),
    ("Zlecenia", "/orders", "list_alt"),
    ("Plany", "/plans", "route"),
    ("Mapa", "/map", "map"),
    ("Raporty", "/reports", "bar_chart"),
    ("Ustawienia", "/settings", "settings"),
]


def _logout() -> None:
    app.storage.user.clear()
    ui.navigate.to("/login")


@contextmanager
def page_frame(title: str) -> Iterator[None]:
    """Wrap page content with the shared header and navigation drawer."""
    with ui.header().classes("items-center justify-between bg-primary"):
        with ui.row().classes("items-center gap-2"):
            ui.button(icon="menu", on_click=lambda: drawer.toggle()).props("flat round color=white")
            ui.label("Crossdock").classes("text-lg font-bold text-white")
            ui.label(title).classes("text-white opacity-80")
        with ui.row().classes("items-center gap-2"):
            ui.icon("person").classes("text-white")
            ui.label(app.storage.user.get("username", "")).classes("text-white")
            ui.button("Wyloguj", icon="logout", on_click=_logout).props("flat color=white")

    # breakpoint=500 keeps the drawer beside the content (no overlay)
    # on typical dispatcher screens.
    with ui.left_drawer(value=True).props("breakpoint=500 bordered").classes("bg-grey-1") as drawer:
        for label, path, icon in NAV_ITEMS:
            with ui.item(on_click=lambda p=path: ui.navigate.to(p)).props("clickable"):
                with ui.item_section().props("avatar"):
                    ui.icon(icon)
                with ui.item_section():
                    ui.item_label(label)

    with ui.column().classes("w-full p-6 gap-4"):
        yield
