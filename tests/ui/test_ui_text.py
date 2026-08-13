"""UI source encoding and self-hosted font checks."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UI_DIR = ROOT / "crossdock" / "ui"
FONT = UI_DIR / "static" / "fonts" / "InterVariable.woff2"

UI_SOURCES = [
    UI_DIR / "pages.py",
    UI_DIR / "layout.py",
    UI_DIR / "ops_dashboard.py",
    UI_DIR / "login_page.py",
    UI_DIR / "labels.py",
    UI_DIR / "widgets.py",
    ROOT / "crossdock" / "text_pl.py",
]


def test_ui_sources_are_utf8_without_replacement() -> None:
    for path in UI_SOURCES:
        text = path.read_text(encoding="utf-8")
        assert "\ufffd" not in text, f"replacement char in {path.name}"


def test_polish_labels_are_intact() -> None:
    pages = (UI_DIR / "pages.py").read_text(encoding="utf-8")
    assert "Usuń zaznaczone" in pages
    assert "Plany FTL" in pages
    assert "FTL (full truckload)" in pages
    assert "Plan transportów całopojazdowych" not in pages
    assert "całopojazdowe" in pages
    assert "wyświetlenia" in pages
    assert "Przesyłki" in pages
    assert "Zapełnienie" in pages
    assert "config/excel_column_mapping.json" not in pages
    assert "config/fleet_seed.json" not in pages
    assert "runtime_settings.json" not in pages
    assert "haversine" not in pages
    assert "(placeholder)" not in pages
    assert "Wczytaj seed" not in pages
    dashboard = (UI_DIR / "ops_dashboard.py").read_text(encoding="utf-8")
    assert "Jedzie (trasy)" in dashboard
    assert "Zostaje w magazynie" in dashboard
    assert "Wszystkie zlecenia" in dashboard


def test_ui_uses_self_hosted_inter_not_georgia() -> None:
    layout = (UI_DIR / "layout.py").read_text(encoding="utf-8")
    assert "Georgia" not in layout
    assert "fonts.google.com" not in layout
    assert "InterVariable.woff2" in layout
    assert FONT.is_file()
    assert FONT.stat().st_size > 100_000
    assert FONT.read_bytes()[:4] == b"wOF2"


def test_selection_column_is_pinned_checkbox() -> None:
    from crossdock.ui.widgets import selection_column

    multi = selection_column(multiple=True)
    assert multi["checkboxSelection"] is True
    assert multi["headerCheckboxSelection"] is True
    assert multi["pinned"] == "left"
    single = selection_column(multiple=False)
    assert "headerCheckboxSelection" not in single


def test_theme_bootstrap_avoids_light_root_when_dark() -> None:
    layout = (UI_DIR / "layout.py").read_text(encoding="utf-8")
    assert "cd-theme" in layout
    assert "localStorage" in layout
    assert ':root:not([data-theme="dark"])' in layout
    assert 'setAttribute("data-theme", "light")' not in layout
    assert "ensure_theme" in layout


def test_dark_html_rewrite_sets_quasar_flags() -> None:
    from crossdock.ui.layout import rewrite_html_for_dark

    src = (
        '<html lang="pl"><head>'
        '<meta id="nicegui-color-scheme" name="color-scheme" content="light" />'
        "</head><body>"
        "const dark = False;"
        "</body></html>"
    )
    out = rewrite_html_for_dark(src)
    assert 'data-theme="dark"' in out
    assert "const dark = True;" in out
    assert 'class="body--dark"' in out
    assert 'content="dark"' in out


def test_orders_hides_tutorial_copy() -> None:
    pages = (UI_DIR / "pages.py").read_text(encoding="utf-8")
    assert "hint_label" not in pages
    assert 'ui.label(\n                "Format: raport e2open' not in pages
    enlarge_calls = pages.count("attach_grid_enlarge(") + pages.count("enlarge_grid_button(")
    assert pages.count("ui.aggrid(") == enlarge_calls
