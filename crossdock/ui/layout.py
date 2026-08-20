"""Shared page frame: Ops Focus top nav + content shell. UI texts in Polish."""

from __future__ import annotations

import html
import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from nicegui import app, ui
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from crossdock.ui.widgets import info_hint

_STATIC_DIR = Path(__file__).resolve().parent / "static"
_static_registered = False
_theme_bootstrap_registered = False

_THEME_BOOTSTRAP_HTML = """
<script>
(function(){
  function readTheme(){
    try {
      var m = document.cookie.match(/(?:^|; )cd-theme=(dark|light)/);
      if (m) return m[1];
    } catch (e) {}
    try {
      var ls = localStorage.getItem('cd-theme');
      if (ls === 'dark' || ls === 'light') return ls;
    } catch (e) {}
    return 'light';
  }
  var t = readTheme();
  var el = document.documentElement;
  el.setAttribute('data-theme', t);
  el.style.colorScheme = t;
  el.style.backgroundColor = t === 'dark' ? '#0b1220' : '#eef2f6';
  function applyBody(){
    if (!document.body) return false;
    document.body.classList.toggle('body--dark', t === 'dark');
    document.body.style.colorScheme = t;
    document.body.style.backgroundColor = t === 'dark' ? '#0b1220' : '#eef2f6';
    return true;
  }
  if (!applyBody()) {
    var obs = new MutationObserver(function(){
      if (applyBody()) obs.disconnect();
    });
    obs.observe(el, {childList: true});
  }
})();
</script>
<style>
html[data-theme="dark"], html[data-theme="dark"] body, body.body--dark {
  background-color: #0b1220 !important;
  color-scheme: dark;
}
html[data-theme="light"], html:not([data-theme]) {
  color-scheme: light;
}
</style>
"""


def register_ui_static() -> None:
    """Serve self-hosted fonts and other UI assets from /static (LAN, no CDN)."""
    global _static_registered
    if _static_registered:
        return
    app.add_static_files("/static", str(_STATIC_DIR))
    _static_registered = True


def rewrite_html_for_dark(text: str) -> str:
    """Force the initial NiceGUI/Quasar document into dark mode."""
    if 'data-theme="dark"' not in text:
        text = text.replace("<html", '<html data-theme="dark"', 1)
    text = text.replace("const dark = False;", "const dark = True;")
    text = text.replace("const dark = None;", "const dark = True;")
    text = re.sub(
        r'(id="nicegui-color-scheme"[^>]*content=")(light|normal)(")',
        r"\1dark\3",
        text,
        count=1,
        flags=re.DOTALL,
    )
    if "body--dark" not in text:
        if "<body>" in text:
            text = text.replace("<body>", '<body class="body--dark">', 1)
        else:
            text = text.replace("<body ", '<body class="body--dark" ', 1)
    return text


class ThemeHtmlMiddleware(BaseHTTPMiddleware):
    """Rewrite the first HTML paint so Quasar/Vue start dark when the cookie says so."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        if request.cookies.get("cd-theme") != "dark":
            return response
        if response.headers.get("X-NiceGUI-Content") != "page":
            return response
        raw = getattr(response, "body", b"") or b""
        if not raw and hasattr(response, "body_iterator"):
            chunks: list[bytes] = []
            async for chunk in response.body_iterator:
                chunks.append(chunk)
            raw = b"".join(chunks)
        if not raw:
            return response
        try:
            text = rewrite_html_for_dark(raw.decode("utf-8"))
        except Exception:
            text = raw.decode("utf-8", errors="replace")
        headers = {
            key: value for key, value in response.headers.items() if key.lower() != "content-length"
        }
        return Response(
            content=text,
            status_code=response.status_code,
            media_type=response.media_type or "text/html",
            headers=headers,
        )


def register_theme_bootstrap() -> None:
    """Inject a blocking head script so dark theme applies before first paint."""
    global _theme_bootstrap_registered
    if _theme_bootstrap_registered:
        return
    ui.add_head_html(_THEME_BOOTSTRAP_HTML, shared=True)
    _theme_bootstrap_registered = True


NAV_ITEMS = [
    ("Pulpit", "/"),
    ("Zlecenia", "/orders"),
    ("Plany", "/plans"),
    ("Mapa", "/map"),
    ("Magazyn", "/warehouse"),
    ("Raporty", "/reports"),
    ("Stan systemu", "/system"),
]

_THEME_CSS = """
@font-face {
  font-family: "Inter";
  src: url("/static/fonts/InterVariable.woff2") format("woff2");
  font-weight: 100 900;
  font-style: normal;
  font-display: swap;
}
:root:not([data-theme="dark"]),
[data-theme="light"] {
  --cd-font: "Inter", system-ui, sans-serif;
  --cd-bg: #eef2f6;
  --cd-card: #ffffff;
  --cd-surface: #eff6ff;
  --cd-border: #dbe3ec;
  --cd-heading: #0f172a;
  --cd-ink: #0f172a;
  --cd-body: #334155;
  --cd-muted: #64748b;
  --cd-accent: #2563eb;
  --cd-accent-text: #1d4ed8;
  --cd-accent-solid: #2563eb;
  --cd-accent-solid-strong: #1d4ed8;
  --cd-accent-soft-bg: #dbeafe;
  --cd-accent-soft-border: #93c5fd;
  --cd-accent-soft-text: #1e40af;
  --cd-badge-free-bg: #dbeafe;
  --cd-badge-free-text: #1e40af;
  --cd-chip-bg: #e2e8f0;
  --cd-chip-text: #475569;
  --cd-warn-bg: #fef3c7;
  --cd-warn-text: #92400e;
  --cd-danger-border: #dc2626;
  --cd-danger-text: #b91c1c;
  --cd-btn-bg: #ffffff;
  --cd-btn-plain-bg: #ffffff;
  --cd-table-head: #f8fafc;
  --cd-rail-track: rgba(37, 99, 235, 0.2);
  --cd-rail-line: rgba(37, 99, 235, 0.3);
  --cd-hero: radial-gradient(1200px 400px at 10% -20%, #dbeafe 0%, transparent 55%),
    linear-gradient(180deg, #ffffff, #f8fafc);
  --cd-shadow-lg: 0 8px 24px rgba(15, 23, 42, 0.06);
  --cd-shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.04);
  --cd-attn-bg: #fff7ed;
  --cd-attn-border: #fed7aa;
  --cd-ride-bg: #eff6ff;
  --cd-ride-border: #93c5fd;
  --cd-hover: #f8fafc;
  --cd-nav-text: #475569;
}
[data-theme="dark"],
html[data-theme="dark"],
body.body--dark {
  --cd-font: "Inter", system-ui, sans-serif;
  --cd-bg: #0b1220;
  --cd-card: #111a2b;
  --cd-surface: #16233b;
  --cd-border: #22304a;
  --cd-heading: #f1f5f9;
  --cd-ink: #e2e8f0;
  --cd-body: #cbd5e1;
  --cd-muted: #94a3b8;
  --cd-accent: #3b82f6;
  --cd-accent-text: #60a5fa;
  --cd-accent-solid: #2563eb;
  --cd-accent-solid-strong: #1d4ed8;
  --cd-accent-soft-bg: #172554;
  --cd-accent-soft-border: #1d4ed8;
  --cd-accent-soft-text: #bfdbfe;
  --cd-badge-free-bg: #1e3a8a;
  --cd-badge-free-text: #bfdbfe;
  --cd-chip-bg: #1f2b40;
  --cd-chip-text: #94a3b8;
  --cd-warn-bg: #3b2f0b;
  --cd-warn-text: #fbbf24;
  --cd-danger-border: #b91c1c;
  --cd-danger-text: #f87171;
  --cd-btn-bg: #16233b;
  --cd-btn-plain-bg: #111a2b;
  --cd-table-head: #16233b;
  --cd-rail-track: rgba(59, 130, 246, 0.25);
  --cd-rail-line: rgba(59, 130, 246, 0.4);
  --cd-hero: radial-gradient(1200px 400px at 10% -20%, #1e3a8a 0%, transparent 55%),
    linear-gradient(180deg, #131f33, #0e1728);
  --cd-shadow-lg: 0 8px 24px rgba(2, 6, 23, 0.45);
  --cd-shadow-sm: 0 1px 2px rgba(2, 6, 23, 0.5);
  --cd-attn-bg: #3b2f0b;
  --cd-attn-border: #92400e;
  --cd-ride-bg: #16233b;
  --cd-ride-border: #1d4ed8;
  --cd-hover: #16233b;
  --cd-nav-text: #94a3b8;
}
html[data-theme="dark"],
html[data-theme="dark"] body,
body.body--dark {
  background: var(--cd-bg) !important;
  color-scheme: dark;
}
body, .nicegui-content, .q-page, .q-layout {
  background: var(--cd-bg) !important;
  color: var(--cd-ink) !important;
  font-family: var(--cd-font) !important;
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
  font-family: var(--cd-font) !important;
}
.cd-logo {
  font-weight: 700 !important;
  color: var(--cd-accent-text) !important;
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
  font-family: var(--cd-font) !important;
  font-size: 0.75rem !important;
  text-decoration: none !important;
  color: var(--cd-nav-text) !important;
  padding: 0.4rem 0.7rem !important;
  border-radius: 999px !important;
  border: 1px solid transparent !important;
  background: transparent !important;
  cursor: pointer !important;
  font-weight: 500 !important;
  line-height: 1.2 !important;
}
.cd-pill-link:hover { background: var(--cd-hover) !important; }
.cd-pill-link.cd-pill-active {
  background: var(--cd-accent-soft-bg) !important;
  border-color: var(--cd-accent-soft-border) !important;
  color: var(--cd-accent-soft-text) !important;
  font-weight: 600 !important;
}
.cd-top-user {
  display: flex !important;
  align-items: center !important;
  gap: 0.5rem !important;
  font-family: var(--cd-font) !important;
  color: var(--cd-muted) !important;
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
  font-family: var(--cd-font);
  color: var(--cd-ink);
}
.cd-shell, .cd-shell * { box-sizing: border-box; }
.cd-shell .ui-sans,
.cd-shell .q-btn,
.cd-shell .q-field,
.cd-shell .q-tab,
.cd-shell .ag-root-wrapper {
  font-family: var(--cd-font) !important;
}
.cd-ops-title-wrap { width: 100% !important; }
.cd-ops-title-row {
  display: flex !important;
  align-items: center !important;
  gap: 0.35rem !important;
  flex-wrap: wrap !important;
}
.cd-ops-title {
  font-size: 2.125rem !important;
  font-weight: 500 !important;
  letter-spacing: -0.02em;
  line-height: 1.15;
  margin: 0 !important;
  color: var(--cd-heading) !important;
  font-family: var(--cd-font) !important;
}
.cd-ops-lead {
  font-family: var(--cd-font) !important;
  color: var(--cd-muted) !important;
  font-size: 0.875rem !important;
  margin: 0 0 0.25rem 0 !important;
  max-width: 42rem;
  line-height: 1.45;
}
.cd-ops-hero {
  display: block !important;
  width: 100% !important;
  background: var(--cd-hero) !important;
  border: 1px solid var(--cd-border) !important;
  border-radius: 20px !important;
  padding: 1.25rem 1.35rem !important;
  box-shadow: var(--cd-shadow-lg) !important;
}
.cd-ops-panel {
  display: block !important;
  width: 100% !important;
  background: var(--cd-card) !important;
  border: 1px solid var(--cd-border) !important;
  border-radius: 16px !important;
  padding: 1.1rem 1.25rem !important;
  box-shadow: var(--cd-shadow-sm) !important;
  font-family: var(--cd-font) !important;
  color: var(--cd-ink) !important;
}
.cd-ops-eyebrow {
  font-family: var(--cd-font) !important;
  font-size: 0.7rem !important;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--cd-accent-text) !important;
  font-weight: 700 !important;
  margin: 0 0 0.4rem 0 !important;
}
.cd-ops-plan-title {
  font-size: 1.75rem !important;
  font-weight: 500 !important;
  margin: 0 !important;
  color: var(--cd-heading) !important;
}
.cd-plan-select {
  min-width: min(100%, 36rem) !important;
  width: 100% !important;
  max-width: 100% !important;
}
.cd-plan-select .q-field__native,
.cd-plan-select .q-field__input,
.cd-plan-select .q-field__control-container {
  overflow: visible !important;
  text-overflow: clip !important;
  white-space: nowrap !important;
}
.cd-plan-select .q-field__control {
  min-height: 2.75rem !important;
  height: auto !important;
}
.cd-plan-select-popup {
  min-width: 36rem !important;
  max-width: min(92vw, 48rem) !important;
}
.cd-wh-card {
  font-family: var(--cd-font) !important;
  background: var(--cd-card) !important;
  border: 1px solid var(--cd-border) !important;
  border-radius: 14px !important;
  padding: 1rem 1.1rem 1.1rem !important;
  margin-bottom: 0.85rem !important;
}
.cd-wh-card-title {
  font-size: 1.05rem !important;
  font-weight: 600 !important;
  color: var(--cd-heading) !important;
  margin: 0 !important;
}
.cd-ops-in-transit {
  margin-top: 0.75rem !important;
  padding-top: 0.75rem !important;
  border-top: 1px solid var(--cd-border) !important;
}
.cd-in-transit-radio .q-radio {
  padding: 0.2rem 0 !important;
}
.cd-ops-plan-sub {
  font-family: var(--cd-font) !important;
  color: var(--cd-muted) !important;
  font-size: 0.8125rem !important;
  margin-top: 0.25rem !important;
}
.cd-ops-pill {
  font-family: var(--cd-font) !important;
  background: var(--cd-accent-solid) !important;
  color: #fff !important;
  border-radius: 999px !important;
  padding: 0.4rem 0.75rem !important;
  font-size: 0.75rem !important;
  font-weight: 600 !important;
  line-height: 1.2 !important;
  display: inline-block !important;
}
.cd-ops-pill-muted {
  font-family: var(--cd-font) !important;
  background: var(--cd-chip-bg) !important;
  color: var(--cd-chip-text) !important;
  border-radius: 999px !important;
  padding: 0.4rem 0.75rem !important;
  font-size: 0.75rem !important;
  font-weight: 600 !important;
  display: inline-block !important;
}
.cd-ops-tri {
  display: grid !important;
  grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
  gap: 0.75rem !important;
  margin-top: 1.25rem !important;
  width: 100% !important;
  align-items: stretch !important;
}
.cd-ops-col {
  border-radius: 14px !important;
  padding: 1rem !important;
  border: 1px solid var(--cd-border) !important;
  background: var(--cd-card) !important;
  min-width: 0 !important;
  min-height: 7.5rem !important;
  height: 100% !important;
  display: flex !important;
  flex-direction: column !important;
}
.cd-ops-col-head {
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
  gap: 0.35rem !important;
  margin-bottom: 0.5rem !important;
  flex-wrap: wrap !important;
}
.cd-ops-col-ride {
  background: var(--cd-ride-bg) !important;
  border-color: var(--cd-ride-border) !important;
}
.cd-ops-col-attn {
  background: var(--cd-attn-bg) !important;
  border-color: var(--cd-attn-border) !important;
}
.cd-ops-col-label {
  font-family: var(--cd-font) !important;
  margin: 0 !important;
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
  font-family: var(--cd-font) !important;
  margin: 0 !important;
  font-size: 0.8125rem !important;
  color: var(--cd-body) !important;
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
  font-family: var(--cd-font) !important;
  border-radius: 10px !important;
  font-weight: 600 !important;
  text-transform: none !important;
}
.cd-ops-kpis {
  display: grid !important;
  grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
  gap: 0.65rem !important;
  margin-bottom: 0.25rem !important;
  width: 100% !important;
}
.cd-ops-kpi {
  font-family: var(--cd-font) !important;
  background: var(--cd-card) !important;
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
  display: grid !important;
  grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
  gap: 0.75rem !important;
  width: 100% !important;
  align-items: stretch !important;
}
.cd-ops-card {
  font-family: var(--cd-font) !important;
  background: var(--cd-card) !important;
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
  color: var(--cd-body) !important;
  line-height: 1.4 !important;
}
.cd-toolbar {
  display: flex !important;
  flex-wrap: wrap !important;
  gap: 0.5rem !important;
  align-items: center !important;
}
.cd-upload-hidden input[type=file] { display: none; }
.cd-card, .cd-card-info {
  background: var(--cd-card) !important;
  border: 1px solid var(--cd-border) !important;
  border-radius: 16px !important;
  padding: 1.1rem 1.25rem !important;
  box-shadow: var(--cd-shadow-sm) !important;
  font-family: var(--cd-font) !important;
}
.cd-card-info {
  background: var(--cd-hero) !important;
}
.cd-stat {
  background: var(--cd-card) !important;
  border: 1px solid var(--cd-border) !important;
  border-radius: 12px !important;
  padding: 0.9rem 1rem !important;
  min-width: 140px;
  flex: 1 1 140px;
  font-family: var(--cd-font) !important;
}
.cd-stat-value { font-size: 1.5rem; font-weight: 700; color: var(--cd-ink); }
.cd-stat-label { font-size: 0.8rem; color: var(--cd-muted); margin-top: 0.15rem; }
.cd-login-wrap {
  width: 100% !important;
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
  background: var(--cd-card) !important;
  border: 1px solid var(--cd-border) !important;
  border-radius: 20px !important;
  padding: 1.75rem 1.5rem !important;
  box-shadow: var(--cd-shadow-lg) !important;
  font-family: var(--cd-font) !important;
}
.cd-login-brand {
  font-family: var(--cd-font) !important;
  font-size: 2rem !important;
  font-weight: 500 !important;
  color: var(--cd-heading) !important;
  margin: 0 0 0.35rem 0 !important;
  text-align: center !important;
}
.cd-login-sub {
  text-align: center !important;
  color: var(--cd-muted) !important;
  font-size: 0.875rem !important;
  margin: 0 0 1.25rem 0 !important;
}
/* Fleet split board */
.cd-fleet-board {
  display: grid !important;
  grid-template-columns: 1fr;
  gap: 1rem !important;
  width: 100% !important;
}
@media (min-width: 1024px) {
  .cd-fleet-board {
    grid-template-columns: minmax(220px, 1fr) minmax(0, 2fr) !important;
  }
}
.cd-fleet-col, .cd-routes-col {
  background: var(--cd-card) !important;
  border: 1px solid var(--cd-border) !important;
  border-radius: 16px !important;
  box-shadow: var(--cd-shadow-sm) !important;
  overflow: hidden !important;
  font-family: var(--cd-font) !important;
  display: flex !important;
  flex-direction: column !important;
  min-width: 0 !important;
}
.cd-fleet-col-head, .cd-routes-col-head {
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
  gap: 0.5rem !important;
  border-bottom: 1px solid var(--cd-border) !important;
  padding: 0.75rem 1rem !important;
  width: 100% !important;
}
.cd-fleet-col-head h3, .cd-routes-col-head h3 {
  margin: 0 !important;
  font-family: var(--cd-font) !important;
  font-size: 1rem !important;
  font-weight: 700 !important;
  color: var(--cd-heading) !important;
}
.cd-fleet-list {
  width: 100% !important;
  align-self: stretch !important;
  align-items: stretch !important;
  display: flex !important;
  flex-direction: column !important;
}
.cd-fleet-list > * {
  width: 100% !important;
  max-width: 100% !important;
  align-self: stretch !important;
}
.cd-fleet-row {
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
  width: 100% !important;
  max-width: 100% !important;
  align-self: stretch !important;
  box-sizing: border-box !important;
  padding: 0.75rem 1rem !important;
  border-top: 1px solid var(--cd-border) !important;
  position: relative !important;
}
.cd-fleet-row-free {
  background: var(--cd-surface) !important;
}
.cd-fleet-row-free::before {
  content: "" !important;
  position: absolute !important;
  left: 0 !important;
  top: 0 !important;
  bottom: 0 !important;
  width: 2px !important;
  background: var(--cd-rail-line) !important;
}
.cd-badge-free {
  background: var(--cd-badge-free-bg) !important;
  color: var(--cd-badge-free-text) !important;
  border-radius: 999px !important;
  padding: 0.25rem 0.625rem !important;
  font-size: 0.75rem !important;
  font-weight: 600 !important;
}
.cd-badge-busy {
  background: var(--cd-warn-bg) !important;
  color: var(--cd-warn-text) !important;
  border-radius: 999px !important;
  padding: 0.25rem 0.625rem !important;
  font-size: 0.75rem !important;
  font-weight: 600 !important;
}
.cd-badge-approved {
  background: var(--cd-accent-solid) !important;
  color: #fff !important;
  border-radius: 999px !important;
  padding: 0.25rem 0.625rem !important;
  font-size: 0.75rem !important;
  font-weight: 600 !important;
}
.cd-badge-proposed {
  background: var(--cd-chip-bg) !important;
  color: var(--cd-chip-text) !important;
  border-radius: 999px !important;
  padding: 0.25rem 0.625rem !important;
  font-size: 0.75rem !important;
  font-weight: 600 !important;
}
.ag-row.cd-row-approved {
  background: var(--cd-ride-bg) !important;
  border-left: 3px solid var(--cd-accent-solid) !important;
}
.ag-row.cd-row-completed {
  background: var(--cd-chip-bg) !important;
  border-left: 3px solid var(--cd-muted) !important;
}
.ag-row.cd-row-proposed {
  background: var(--cd-card) !important;
}
.ag-row.cd-row-lowfill {
  border-left: 3px solid var(--cd-warn-text, #b45309) !important;
}
/* AG Grid dark/light */
.ag-theme-alpine,
.ag-theme-alpine-dark,
.cd-shell .ag-root-wrapper,
.ag-header-cell-label,
.ag-cell {
  font-family: var(--cd-font) !important;
}
.ag-theme-alpine,
.ag-theme-alpine-dark,
.cd-shell .ag-root-wrapper {
  --ag-background-color: var(--cd-card) !important;
  --ag-foreground-color: var(--cd-ink) !important;
  --ag-header-background-color: var(--cd-table-head) !important;
  --ag-header-foreground-color: var(--cd-muted) !important;
  --ag-border-color: var(--cd-border) !important;
  --ag-row-hover-color: var(--cd-hover) !important;
  --ag-selected-row-background-color: var(--cd-surface) !important;
  --ag-odd-row-background-color: var(--cd-card) !important;
}
.text-gray-700, .text-gray-600, .text-gray-500, .text-gray-400 {
  color: var(--cd-muted) !important;
}
.text-red-700 {
  color: var(--cd-danger-text) !important;
}
.cd-info-btn {
  color: var(--cd-muted) !important;
  min-width: 1.75rem !important;
  min-height: 1.75rem !important;
}
.cd-info-menu {
  max-width: 22rem !important;
}
.cd-info-text {
  display: block !important;
  max-width: 20rem;
  white-space: normal !important;
  font-size: 0.8125rem !important;
  line-height: 1.45 !important;
  padding: 0.35rem 0.5rem !important;
  color: var(--cd-body) !important;
  font-family: var(--cd-font) !important;
}
.cd-tab-tools {
  display: flex !important;
  align-items: center !important;
  justify-content: flex-end !important;
  gap: 0.25rem !important;
  width: 100% !important;
}
.cd-enlarge-card {
  width: 90vw !important;
  max-width: 90vw !important;
  height: 85vh !important;
  max-height: 85vh !important;
  display: flex !important;
  flex-direction: column !important;
  padding: 1rem 1.15rem !important;
  font-family: var(--cd-font) !important;
}
.cd-enlarge-head { flex: 0 0 auto !important; }
.cd-enlarge-title {
  font-size: 1.125rem !important;
  font-weight: 600 !important;
  color: var(--cd-heading) !important;
  font-family: var(--cd-font) !important;
}
.cd-enlarge-host {
  flex: 1 1 auto !important;
  min-height: 0 !important;
  width: 100% !important;
}
.cd-grid-host { width: 100% !important; }
.cd-map-legend {
  min-width: 220px !important;
  max-width: 280px !important;
  flex: 0 0 auto !important;
  padding: 0.75rem 1rem !important;
  max-height: 70vh !important;
  overflow-y: auto !important;
}
.cd-map-legend-row {
  display: flex !important;
  align-items: center !important;
  gap: 0.35rem !important;
  width: 100% !important;
  cursor: pointer !important;
  border-radius: 4px !important;
  padding: 0.15rem 0.25rem !important;
}
.cd-map-legend-row:hover {
  background: color-mix(in srgb, var(--cd-heading) 8%, transparent) !important;
}
.cd-map-legend-row.cd-map-legend-active {
  background: color-mix(in srgb, var(--cd-heading) 14%, transparent) !important;
}
.cd-map-legend-swatch {
  width: 14px !important;
  height: 14px !important;
  border-radius: 2px !important;
  flex: 0 0 auto !important;
}
.cd-map-legend-label {
  font-size: 0.8125rem !important;
  color: var(--cd-body) !important;
  line-height: 1.25 !important;
  flex: 1 1 auto !important;
}
.cd-map-host {
  flex: 1 1 auto !important;
  min-width: 320px !important;
  width: 100% !important;
}
.cd-map-seq-badge {
  background: var(--badge-bg, #377eb8) !important;
  color: #fff !important;
  border: 2px solid #fff !important;
  border-radius: 50% !important;
  width: 22px !important;
  height: 22px !important;
  font-size: 11px !important;
  font-weight: 700 !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  box-shadow: 0 1px 3px rgba(0,0,0,0.35) !important;
  font-family: var(--cd-font) !important;
}
.cd-plan-meta {
  display: flex !important;
  flex-wrap: wrap !important;
  align-items: stretch !important;
  gap: 0.5rem !important;
  width: 100% !important;
  min-height: 3.25rem !important;
  padding: 0.6rem 0.75rem !important;
  background: var(--cd-surface) !important;
  border: 1px solid var(--cd-border) !important;
  border-radius: 14px !important;
  box-sizing: border-box !important;
}
.cd-plan-chip {
  display: flex !important;
  flex-direction: column !important;
  justify-content: center !important;
  gap: 0.1rem !important;
  padding: 0.3rem 0.7rem !important;
  border-radius: 10px !important;
  background: var(--cd-card) !important;
  border: 1px solid var(--cd-border) !important;
  min-height: 2.5rem !important;
}
.cd-plan-chip-k {
  font-size: 0.65rem !important;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--cd-muted) !important;
  font-weight: 600 !important;
  margin: 0 !important;
  line-height: 1.2 !important;
}
.cd-plan-chip-v {
  font-size: 0.9375rem !important;
  font-weight: 600 !important;
  color: var(--cd-heading) !important;
  margin: 0 !important;
  line-height: 1.25 !important;
}
.cd-plan-chip-muted {
  background: transparent !important;
  border-style: dashed !important;
}
.cd-plan-chip-muted .cd-plan-chip-v {
  color: var(--cd-muted) !important;
  font-weight: 500 !important;
  font-size: 0.8125rem !important;
}
@media (max-width: 800px) {
  .cd-ops-tri, .cd-ops-kpis, .cd-ops-foot {
    grid-template-columns: 1fr !important;
  }
}
"""

_theme_ready = False


def _theme_from_cookie() -> str | None:
    try:
        raw = ui.context.client.request.cookies.get("cd-theme")
    except Exception:
        return None
    return raw if raw in {"dark", "light"} else None


def _resolve_theme() -> str:
    raw = app.storage.user.get("theme")
    if raw in {"dark", "light"}:
        return raw
    cookie = _theme_from_cookie()
    if cookie is not None:
        return cookie
    return "light"


def _current_theme() -> str:
    return _resolve_theme()


def _persist_theme_client(theme: str) -> None:
    ui.run_javascript(
        f"""
        (function(t){{
          document.documentElement.setAttribute('data-theme', t);
          document.documentElement.style.colorScheme = t;
          try {{ localStorage.setItem('cd-theme', t); }} catch (e) {{}}
          document.cookie = 'cd-theme=' + t + '; path=/; SameSite=Lax; max-age=31536000';
          if (document.body) {{
            document.body.classList.toggle('body--dark', t === 'dark');
            document.body.style.colorScheme = t;
          }}
        }})({theme!r});
        """
    )


def _enable_quasar_dark(theme: str) -> None:
    mode = ui.dark_mode()
    if theme == "dark":
        mode.enable()
    else:
        mode.disable()


def _install_theme_assets() -> None:
    global _theme_ready
    register_theme_bootstrap()
    if not _theme_ready:
        ui.colors(
            primary="#2563eb",
            secondary="#334155",
            accent="#3b82f6",
            positive="#15803d",
            negative="#b91c1c",
            info="#0369a1",
            warning="#b45309",
        )
        _theme_ready = True
    register_ui_static()
    ui.add_css(_THEME_CSS)


def _apply_theme(theme: str) -> None:
    theme = "dark" if theme == "dark" else "light"
    app.storage.user["theme"] = theme
    _enable_quasar_dark(theme)
    _persist_theme_client(theme)


def _toggle_theme() -> None:
    nxt = "light" if _current_theme() == "dark" else "dark"
    _apply_theme(nxt)
    ui.navigate.reload()


def _ensure_theme() -> None:
    theme = _resolve_theme()
    app.storage.user["theme"] = theme
    _enable_quasar_dark(theme)
    _install_theme_assets()
    _persist_theme_client(theme)


def ensure_theme() -> None:
    """Login chrome: keep CSS, do not overwrite a saved dark theme."""
    _install_theme_assets()
    saved = app.storage.user.get("theme") or _theme_from_cookie()
    if saved == "dark":
        _enable_quasar_dark("dark")
        _persist_theme_client("dark")


def _logout() -> None:
    theme = app.storage.user.get("theme")
    app.storage.user.clear()
    if theme in {"dark", "light"}:
        app.storage.user["theme"] = theme
    ui.navigate.to("/login")


def ops_page_header(title: str, lead: str) -> None:
    """Page title with explanation hidden behind an info control."""
    with (
        ui.element("div").classes("cd-ops-title-wrap"),
        ui.row().classes("cd-ops-title-row items-center"),
    ):
        ui.html(
            f"<h1 class='cd-ops-title'>{html.escape(title)}</h1>",
            sanitize=False,
        )
        if lead:
            info_hint(lead)


@contextmanager
def page_frame(title: str) -> Iterator[None]:
    """Wrap page content with Ops Focus top pill nav and centered shell."""
    _ensure_theme()
    theme = _current_theme()
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
            theme_label = "Jasny" if theme == "dark" else "Ciemny"
            theme_icon = "light_mode" if theme == "dark" else "dark_mode"
            ui.button(
                theme_label,
                icon=theme_icon,
                on_click=_toggle_theme,
            ).props(
                f"flat dense no-caps outline aria-label="
                f'"{"Włącz jasny tryb" if theme == "dark" else "Włącz ciemny tryb"}"'
            )
            settings_active = "cd-pill-active" if title == "Ustawienia" else ""
            ui.button(
                "Ustawienia",
                icon="settings",
                on_click=lambda: ui.navigate.to("/settings"),
            ).props("flat dense no-caps").classes(settings_active)
            ui.label(app.storage.user.get("username", "") or "—")
            ui.button("Wyloguj", on_click=_logout).props("flat dense no-caps color=primary")

    with ui.column().classes("cd-shell w-full"):
        yield
