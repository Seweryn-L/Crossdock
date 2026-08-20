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
    assert "Operacje dnia" in pages
    assert "Generuj" in pages
    assert "całopojazdowe" not in pages or "FTL" in pages
    assert "wyświetlenia" in pages
    assert "Przesyłki" in pages
    assert "Zapełnienie" in pages
    assert "Nowa pusta generacja" in pages
    assert "Wynik importu" in pages
    assert "Historia generacji" in pages
    assert "Pokaż log" in pages
    assert "Już w systemie" in pages
    assert "config/excel_column_mapping.json" not in pages
    assert "config/fleet_seed.json" not in pages
    assert "runtime_settings.json" not in pages
    assert "haversine" not in pages
    assert "(placeholder)" not in pages
    assert "Wczytaj seed" not in pages
    layout = (UI_DIR / "layout.py").read_text(encoding="utf-8")
    assert '("Operacje", "/plans")' in layout
    dashboard = (UI_DIR / "ops_dashboard.py").read_text(encoding="utf-8")
    assert "Jedzie (trasy)" in dashboard
    assert "Zostaje w magazynie" in dashboard
    assert "Wszystkie zlecenia" in dashboard
    assert "Stan operacyjny" in dashboard
    assert "Otwórz operacje" in dashboard
    assert "Aktywny plan" not in dashboard
    assert "Trasy w drodze" in dashboard
    assert "Zrealizowane" in pages
    assert "Do kolejki" in pages
    assert "Kolejka wydań" in pages
    assert "W drodze" in pages
    assert (
        "Kolejka magazynowa"
        not in pages.split("async def warehouse_page")[1].split("def _load_warehouse_view")[0]
    )


def test_plan_label_format() -> None:
    from datetime import datetime

    from crossdock.text_pl import format_plan_label

    stamp = datetime(2026, 8, 13, 14, 22)
    named = format_plan_label(
        run_id=3,
        display_name="Tydzień 12-18.06",
        plan_status="draft",
        created_at=stamp,
    )
    assert named == "Tydzień 12-18.06 · #3 · roboczy · 13.08 14:22"
    unnamed = format_plan_label(
        run_id=3,
        display_name=None,
        plan_status="draft",
        created_at=stamp,
    )
    assert unnamed == "Generacja #3 · roboczy · 13.08 14:22"


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
    ops_dashboard = (UI_DIR / "ops_dashboard.py").read_text(encoding="utf-8")
    assert "hint_label" not in pages
    assert 'ui.label(\n                "Format: raport e2open' not in pages
    aggrid_calls = pages.count("ui.aggrid(") + ops_dashboard.count("ui.aggrid(")
    enlarge_calls = (
        pages.count("attach_grid_enlarge(")
        + pages.count("enlarge_grid_button(")
        + ops_dashboard.count("attach_grid_enlarge(")
        + pages.count("def open_route_enlarge(")
    )
    assert aggrid_calls == enlarge_calls


def test_plan_generation_keeps_sqlite_off_cpu_bound() -> None:
    pages = (UI_DIR / "pages.py").read_text(encoding="utf-8")
    # Staged pipeline: solvers stay in cpu_bound; OSRM/DB stay in io_bound.
    assert "run.cpu_bound(solve_assignment_stage" in pages
    assert "run.cpu_bound(solve_routes_stage" in pages
    assert "_build_routing_bundle_job" in pages
    assert "run.io_bound(\n                        _build_routing_bundle_job" in pages
    assert "_finalize_plan_job" in pages
    assert "run.io_bound(\n                        _finalize_plan_job" in pages
    assert "run.io_bound(_persist_plan_job" in pages
    assert "_run_plan_job" not in pages
    assert "run.cpu_bound(_run_plan_job" not in pages
    assert "run.cpu_bound(solve_prepared_plan" not in pages


def test_warehouse_does_not_propose_on_load() -> None:
    pages = (UI_DIR / "pages.py").read_text(encoding="utf-8")
    warehouse = pages.split("async def warehouse_page")[1].split("def _load_warehouse_view")[0]
    last = warehouse.rstrip().splitlines()[-1].strip()
    assert last == "await refresh_all()"
    assert "compute_buffer_proposals" in pages
    assert "propose_buffering" not in pages
