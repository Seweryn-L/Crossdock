"""Shared page frame: Ops Focus top nav + content shell. UI texts in Polish."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from nicegui import app, ui

NAV_ITEMS = [
    ("Pulpit", "/"),
    ("Zlecenia", "/orders"),
    ("Plany", "/plans"),
    ("Mapa", "/map"),
    ("Magazyn", "/warehouse"),
    ("Raporty", "/reports"),
    ("Stan systemu", "/system"),
    ("Ustawienia", "/settings"),
]

_THEME_CSS = """
:root {
  --cd-bg: #eef2f6;
  --cd-card: #ffffff;
  --cd-border: #dbe3ec;
  --cd-muted: #64748b;
  --cd-accent: #0f766e;
  --cd-ink: #0f172a;
}
body, .nicegui-content, .q-page, .q-layout {
  background: var(--cd-bg) !important;
}
.q-header { display: none !important; }
.cd-topbar {
  display: flex !important;
  flex-wrap: wrap !important;
  align-items: center !important;
  justify-content: space-between !important;
  gap: 0.75rem 1rem !important;
  width: 100% !important;
  max-width: 1100px !important;
  margin: 0 auto !important;
  padding: 1.1rem 1.25rem 0.35rem !important;
  font-family: "Segoe UI", system-ui, sans-serif !important;
}
.cd-logo {
  font-weight: 700 !important;
  color: var(--cd-accent) !important;
  font-size: 0.875rem !important;
  letter-spacing: 0.08em !important;
  text-transform: uppercase !important;
  margin: 0 !important;
}
.cd-pill-nav {
  display: flex !important;
  flex-wrap: wrap !important;
  gap: 0.35rem !important;
  align-items: center !important;
  flex: 1 1 auto !important;
  justify-content: center !important;
}
.cd-pill-link {
  font-family: "Segoe UI", system-ui, sans-serif !important;
  font-size: 0.75rem !important;
  text-decoration: none !important;
  color: #475569 !important;
  padding: 0.4rem 0.7rem !important;
  border-radius: 999px !important;
  border: 1px solid transparent !important;
  background: transparent !important;
  cursor: pointer !important;
  font-weight: 500 !important;
  line-height: 1.2 !important;
}
.cd-pill-link:hover { background: #f8fafc !important; }
.cd-pill-link.cd-pill-active {
  background: #ccfbf1 !important;
  border-color: #99f6e4 !important;
  color: #115e59 !important;
  font-weight: 600 !important;
}
.cd-top-user {
  display: flex !important;
  align-items: center !important;
  gap: 0.5rem !important;
  font-family: "Segoe UI", system-ui, sans-serif !important;
  color: #475569 !important;
  font-size: 0.8125rem !important;
}
.cd-top-user .q-btn {
  text-transform: none !important;
  font-weight: 600 !important;
}
.cd-shell {
  width: 100% !important;
  max-width: 1100px !important;
  margin: 0 auto !important;
  padding: 0.75rem 1.25rem 2.5rem !important;
  display: flex !important;
  flex-direction: column !important;
  gap: 1rem !important;
  font-family: Georgia, "Iowan Old Style", "Times New Roman", serif;
  color: var(--cd-ink);
}
.cd-shell, .cd-shell * { box-sizing: border-box; }
.cd-shell .ui-sans,
.cd-shell .q-btn,
.cd-shell .q-field,
.cd-shell .q-tab,
.cd-shell .ag-root-wrapper {
  font-family: "Segoe UI", system-ui, sans-serif !important;
}
.cd-ops-title {
  font-size: 2.125rem !important;
  font-weight: 500 !important;
  letter-spacing: -0.02em;
  line-height: 1.15;
  margin: 0 0 0.35rem 0 !important;
  color: var(--cd-ink) !important;
  font-family: Georgia, "Iowan Old Style", "Times New Roman", serif !important;
}
.cd-ops-lead {
  font-family: "Segoe UI", system-ui, sans-serif !important;
  color: var(--cd-muted) !important;
  font-size: 0.875rem !important;
  margin: 0 0 0.25rem 0 !important;
  max-width: 42rem;
  line-height: 1.45;
}
.cd-ops-hero {
  display: block !important;
  width: 100% !important;
  background:
    radial-gradient(1200px 400px at 10% -20%, #ccfbf1 0%, transparent 55%),
    linear-gradient(180deg, #ffffff, #f8fafc) !important;
  border: 1px solid var(--cd-border) !important;
  border-radius: 20px !important;
  padding: 1.25rem 1.35rem !important;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04) !important;
}
.cd-ops-panel {
  display: block !important;
  width: 100% !important;
  background: #fff !important;
  border: 1px solid var(--cd-border) !important;
  border-radius: 16px !important;
  padding: 1.1rem 1.25rem !important;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04) !important;
  font-family: "Segoe UI", system-ui, sans-serif !important;
}
.cd-ops-eyebrow {
  font-family: "Segoe UI", system-ui, sans-serif !important;
  font-size: 0.7rem !important;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--cd-accent) !important;
  font-weight: 700 !important;
  margin: 0 0 0.4rem 0 !important;
}
.cd-ops-plan-title {
  font-size: 1.75rem !important;
  font-weight: 500 !important;
  margin: 0 !important;
  color: var(--cd-ink) !important;
}
.cd-ops-plan-sub {
  font-family: "Segoe UI", system-ui, sans-serif !important;
  color: var(--cd-muted) !important;
  font-size: 0.8125rem !important;
  margin-top: 0.25rem !important;
}
.cd-ops-pill {
  font-family: "Segoe UI", system-ui, sans-serif !important;
  background: #0f766e !important;
  color: #fff !important;
  border-radius: 999px !important;
  padding: 0.4rem 0.75rem !important;
  font-size: 0.75rem !important;
  font-weight: 600 !important;
  line-height: 1.2 !important;
  display: inline-block !important;
}
.cd-ops-pill-muted {
  font-family: "Segoe UI", system-ui, sans-serif !important;
  background: #e2e8f0 !important;
  color: #475569 !important;
  border-radius: 999px !important;
  padding: 0.4rem 0.75rem !important;
  font-size: 0.75rem !important;
  font-weight: 600 !important;
  display: inline-block !important;
}
.cd-ops-tri {
  display: flex !important;
  flex-wrap: wrap !important;
  gap: 0.75rem !important;
  margin-top: 1.25rem !important;
  width: 100% !important;
}
.cd-ops-col {
  flex: 1 1 160px !important;
  border-radius: 14px !important;
  padding: 1rem !important;
  border: 1px solid var(--cd-border) !important;
  background: #fff !important;
  min-width: 0 !important;
}
.cd-ops-col-ride { background: #f0fdfa !important; border-color: #99f6e4 !important; }
.cd-ops-col-attn { background: #fff7ed !important; border-color: #fed7aa !important; }
.cd-ops-col-label {
  font-family: "Segoe UI", system-ui, sans-serif !important;
  margin: 0 0 0.5rem 0 !important;
  font-size: 0.75rem !important;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--cd-muted) !important;
  font-weight: 600 !important;
}
.cd-ops-col-n {
  font-size: 2.25rem !important;
  line-height: 1 !important;
  margin: 0 0 0.4rem 0 !important;
  font-weight: 500 !important;
  color: var(--cd-ink) !important;
}
.cd-ops-col-hint {
  font-family: "Segoe UI", system-ui, sans-serif !important;
  margin: 0 !important;
  font-size: 0.8125rem !important;
  color: #334155 !important;
}
.cd-ops-cta {
  display: flex !important;
  flex-wrap: wrap !important;
  gap: 0.5rem !important;
  margin-top: 1.15rem !important;
  width: 100% !important;
}
.cd-ops-cta .q-btn,
.cd-toolbar .q-btn {
  font-family: "Segoe UI", system-ui, sans-serif !important;
  border-radius: 10px !important;
  font-weight: 600 !important;
  text-transform: none !important;
}
.cd-ops-kpis {
  display: flex !important;
  flex-wrap: wrap !important;
  gap: 0.65rem !important;
  margin-bottom: 0.25rem !important;
  width: 100% !important;
}
.cd-ops-kpi {
  flex: 1 1 140px !important;
  font-family: "Segoe UI", system-ui, sans-serif !important;
  background: #fff !important;
  border: 1px solid var(--cd-border) !important;
  border-radius: 12px !important;
  padding: 0.9rem !important;
  min-width: 0 !important;
}
.cd-ops-kpi b {
  display: block !important;
  font-size: 1.375rem !important;
  font-weight: 700 !important;
  color: var(--cd-ink) !important;
}
.cd-ops-kpi span {
  display: block !important;
  font-size: 0.75rem !important;
  color: var(--cd-muted) !important;
  margin-top: 0.15rem !important;
}
.cd-ops-foot {
  display: flex !important;
  flex-wrap: wrap !important;
  gap: 0.75rem !important;
  width: 100% !important;
}
.cd-ops-card {
  flex: 1 1 200px !important;
  font-family: "Segoe UI", system-ui, sans-serif !important;
  background: #fff !important;
  border: 1px solid var(--cd-border) !important;
  border-radius: 14px !important;
  padding: 1rem !important;
  min-width: 0 !important;
}
.cd-ops-card h4 {
  margin: 0 0 0.5rem 0 !important;
  font-size: 0.8125rem !important;
  color: var(--cd-muted) !important;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-weight: 600 !important;
}
.cd-ops-card .v {
  font-size: 1.625rem !important;
  font-weight: 700 !important;
  color: var(--cd-ink) !important;
  line-height: 1.1 !important;
}
.cd-ops-card p {
  margin: 0.35rem 0 0 0 !important;
  font-size: 0.8125rem !important;
  color: #334155 !important;
  line-height: 1.4 !important;
}
.cd-toolbar {
  display: flex !important;
  flex-wrap: wrap !important;
  gap: 0.5rem !important;
  align-items: center !important;
}
.cd-upload-hidden input[type=file] { display: none; }
/* Legacy aliases used by older page markup */
.cd-card, .cd-card-info {
  background: #fff !important;
  border: 1px solid var(--cd-border) !important;
  border-radius: 16px !important;
  padding: 1.1rem 1.25rem !important;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04) !important;
  font-family: "Segoe UI", system-ui, sans-serif !important;
}
.cd-card-info {
  background:
    radial-gradient(900px 260px at 8% -30%, #ccfbf1 0%, transparent 55%),
    linear-gradient(180deg, #ffffff, #f8fafc) !important;
}
.cd-stat {
  background: #fff !important;
  border: 1px solid var(--cd-border) !important;
  border-radius: 12px !important;
  padding: 0.9rem 1rem !important;
  min-width: 140px;
  flex: 1 1 140px;
  font-family: "Segoe UI", system-ui, sans-serif !important;
}
.cd-stat-value { font-size: 1.5rem; font-weight: 700; color: var(--cd-ink); }
.cd-stat-label { font-size: 0.8rem; color: var(--cd-muted); margin-top: 0.15rem; }
.cd-login-wrap {
  min-height: 100vh !important;
  background: var(--cd-bg) !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  padding: 2rem !important;
}
.cd-login-card {
  width: 100% !important;
  max-width: 22rem !important;
  background: #fff !important;
  border: 1px solid var(--cd-border) !important;
  border-radius: 20px !important;
  padding: 1.75rem 1.5rem !important;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05) !important;
  font-family: "Segoe UI", system-ui, sans-serif !important;
}
.cd-login-brand {
  font-family: Georgia, "Iowan Old Style", serif !important;
  font-size: 2rem !important;
  font-weight: 500 !important;
  color: var(--cd-ink) !important;
  margin: 0 0 0.35rem 0 !important;
  text-align: center !important;
}
.cd-login-sub {
  text-align: center !important;
  color: var(--cd-muted) !important;
  font-size: 0.875rem !important;
  margin: 0 0 1.25rem 0 !important;
}
"""

_theme_ready = False


def _ensure_theme() -> None:
    global _theme_ready
    if not _theme_ready:
        ui.colors(
            primary="#0f766e",
            secondary="#334155",
            accent="#14b8a6",
            positive="#15803d",
            negative="#b91c1c",
            info="#0369a1",
            warning="#b45309",
        )
        _theme_ready = True
    ui.add_css(_THEME_CSS)


def ensure_theme() -> None:
    """Apply Ops Focus colors + CSS (safe to call from login / pages)."""
    _ensure_theme()


def _logout() -> None:
    app.storage.user.clear()
    ui.navigate.to("/login")


def ops_page_header(title: str, lead: str) -> None:
    """Ops Focus page title + supporting sentence."""
    ui.html(
        f"<h1 class='cd-ops-title'>{title}</h1><p class='cd-ops-lead'>{lead}</p>",
        sanitize=False,
    )


@contextmanager
def page_frame(title: str) -> Iterator[None]:
    """Wrap page content with Ops Focus top pill nav and centered shell."""
    _ensure_theme()
    with ui.element("div").classes("cd-topbar"):
        ui.label("Crossdock").classes("cd-logo")
        with ui.element("div").classes("cd-pill-nav"):
            for label, path in NAV_ITEMS:
                active = "cd-pill-active" if label == title else ""
                ui.button(
                    label,
                    on_click=lambda p=path: ui.navigate.to(p),
                ).props("flat dense no-caps").classes(f"cd-pill-link {active}")
        with ui.element("div").classes("cd-top-user"):
            ui.label(app.storage.user.get("username", "") or "—")
            ui.button("Wyloguj", on_click=_logout).props("flat dense no-caps color=primary")

    with ui.column().classes("cd-shell w-full"):
        yield
