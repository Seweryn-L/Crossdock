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
    ("Magazyn", "/warehouse", "warehouse"),
    ("Stan systemu", "/system", "monitor_heart"),
    ("Ustawienia", "/settings", "settings"),
]

_THEME_CSS = """
:root {
  --cd-bg: #f1f5f9;
  --cd-card: #ffffff;
  --cd-border: #e2e8f0;
  --cd-muted: #64748b;
  --cd-accent: #0f766e;
}
body { background: var(--cd-bg) !important; }
.cd-page { gap: 1rem; }
.cd-card {
  background: var(--cd-card);
  border: 1px solid var(--cd-border);
  border-radius: 12px;
  padding: 1rem 1.25rem;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.cd-card-info {
  background: #f0fdfa;
  border: 1px solid #99f6e4;
  border-radius: 12px;
  padding: 1rem 1.25rem;
}
.cd-toolbar { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; }
.cd-stat {
  background: var(--cd-card);
  border: 1px solid var(--cd-border);
  border-radius: 12px;
  padding: 1rem 1.25rem;
  min-width: 140px;
  flex: 1 1 140px;
}
.cd-stat-value { font-size: 1.5rem; font-weight: 700; color: #0f172a; }
.cd-stat-label { font-size: 0.8rem; color: var(--cd-muted); margin-top: 0.15rem; }
.cd-nav-active { background: #ccfbf1 !important; border-radius: 8px; }
.cd-upload-hidden input[type=file] { display: none; }
"""

_theme_ready = False


def _ensure_theme() -> None:
    global _theme_ready
    if _theme_ready:
        return
    ui.colors(
        primary="#0f766e",
        secondary="#334155",
        accent="#14b8a6",
        positive="#15803d",
        negative="#b91c1c",
        info="#0369a1",
        warning="#b45309",
    )
    ui.add_css(_THEME_CSS)
    _theme_ready = True


def _logout() -> None:
    app.storage.user.clear()
    ui.navigate.to("/login")


@contextmanager
def page_frame(title: str) -> Iterator[None]:
    """Wrap page content with the shared header and navigation drawer."""
    _ensure_theme()
    with ui.header().classes("items-center justify-between"):
        with ui.row().classes("items-center gap-2"):
            ui.button(icon="menu", on_click=lambda: drawer.toggle()).props("flat round color=white")
            ui.label("Crossdock").classes("text-lg font-bold text-white")
            ui.label(title).classes("text-white opacity-80")
        with ui.row().classes("items-center gap-2"):
            ui.icon("person").classes("text-white")
            ui.label(app.storage.user.get("username", "")).classes("text-white")
            ui.button("Wyloguj", icon="logout", on_click=_logout).props("flat color=white")

    with (
        ui.left_drawer(value=True).props("breakpoint=500 bordered").classes("bg-slate-50") as drawer
    ):
        for label, path, icon in NAV_ITEMS:
            active = label == title
            item_props = "clickable"
            with (
                ui.item(on_click=lambda p=path: ui.navigate.to(p))
                .props(item_props)
                .classes("cd-nav-active" if active else "")
            ):
                with ui.item_section().props("avatar"):
                    ui.icon(icon)
                with ui.item_section():
                    ui.item_label(label)

    with ui.column().classes("w-full p-6 gap-4 cd-page"):
        yield
