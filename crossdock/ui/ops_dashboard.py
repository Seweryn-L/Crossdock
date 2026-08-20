"""Ops Focus dashboard renderer (Magic Patterns Concept B)."""

from __future__ import annotations

import html
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from nicegui import ui

from crossdock.services.dashboard import DashboardSnapshot
from crossdock.text_pl import route_status_pl
from crossdock.ui.layout import ops_page_header
from crossdock.ui.widgets import attach_grid_enlarge, info_hint, selection_column


def _status_tile(label: str, value: int, hint: str, extra_class: str = "") -> None:
    with ui.element("div").classes(f"cd-ops-col {extra_class}".strip()):
        with ui.element("div").classes("cd-ops-col-head"):
            ui.label(label).classes("cd-ops-col-label")
            info_hint(hint)
        ui.label(str(value)).classes("cd-ops-col-n")


def render_ops_focus_dashboard(
    snap: DashboardSnapshot,
    *,
    on_enqueue_staying: Callable[[], Awaitable[Any] | Any],
    open_map: Callable[[], None],
    on_complete_routes: Callable[[Sequence[int]], Awaitable[Any] | Any] | None = None,
) -> None:
    """Paint the Ops Focus home layout inside an already-open page_frame."""
    plan_title = snap.plan_label or "Brak stanu operacyjnego"
    plan_sub = (
        f"status: {snap.latest_plan_status_pl or '—'}"
        if snap.latest_plan_id is not None
        else "Wygeneruj pierwszą propozycję tras w sekcji Operacje."
    )
    if snap.latest_plan_id is None:
        pill = '<span class="cd-ops-pill-muted">Brak danych</span>'
    elif (snap.attention or 0) > 0:
        pill = '<span class="cd-ops-pill">Wymaga decyzji</span>'
    else:
        status = html.escape(snap.latest_plan_status_pl or "OK")
        pill = f'<span class="cd-ops-pill-muted">{status}</span>'

    import_txt = html.escape(snap.last_import_summary or "Brak danych w audycie.")
    plan_title_e = html.escape(plan_title)
    plan_sub_e = html.escape(plan_sub)

    ops_page_header(
        "Pulpit dyspozytora",
        "Codzienny stan operacyjny: import, Generuj, zatwierdzanie tras, mapa i magazyn.",
    )

    with ui.element("div").classes("cd-ops-hero"):
        with ui.row().classes("w-full items-start justify-between flex-wrap gap-4"):
            with ui.column().classes("gap-1").style("min-width:min(100%, 40rem);flex:1;"):
                ui.label("Stan operacyjny").classes("cd-ops-eyebrow")
                ui.html(f"<h2 class='cd-ops-plan-title'>{plan_title_e}</h2>", sanitize=False)
                ui.html(f"<div class='cd-ops-plan-sub'>{plan_sub_e}</div>", sanitize=False)
            ui.html(pill, sanitize=False)
        with ui.element("div").classes("cd-ops-tri"):
            _status_tile(
                "Jedzie (trasy)",
                snap.riding,
                "trasy gotowe do zatwierdzenia lub już zatwierdzone",
                "cd-ops-col-ride",
            )
            _status_tile(
                "Zostaje w magazynie",
                snap.staying,
                "do kolejki magazynowej",
            )
            _status_tile(
                "Wymaga uwagi",
                snap.attention,
                "brak współrzędnych / limity",
                "cd-ops-col-attn",
            )
        with ui.row().classes("cd-ops-cta ui-sans"):
            ui.button(
                "Otwórz operacje",
                on_click=lambda: ui.navigate.to("/plans"),
            ).props("color=primary no-caps")
            ui.button(
                "Dodaj zostające do kolejki",
                on_click=on_enqueue_staying,
            ).props("outline color=primary no-caps")
            ui.button(
                "Pokaż na mapie",
                on_click=open_map,
            ).props("outline color=primary no-caps")

        with ui.element("div").classes("cd-ops-in-transit w-full"):
            with ui.row().classes("w-full items-center justify-between"):
                with ui.row().classes("items-center gap-1"):
                    ui.label("Trasy w drodze").classes("cd-wh-card-title")
                    info_hint(
                        "Zatwierdzone trasy bieżącego stanu, które jeszcze nie wróciły. "
                        "Zrealizowane zwalnia auto i oznacza zlecenia jako dostarczone."
                    )
                enlarge_transit_btn = ui.button("Powiększ", icon="open_in_full").props(
                    "flat dense no-caps"
                )
            if snap.in_transit:
                transit_host = ui.element("div").classes("cd-grid-host")
                with transit_host:
                    transit_grid = (
                        ui.aggrid(
                            {
                                "columnDefs": [
                                    selection_column(multiple=True),
                                    {
                                        "headerName": "Pojazd",
                                        "field": "vehicle",
                                        "filter": True,
                                    },
                                    {
                                        "headerName": "Rozładunki",
                                        "field": "drop_summary",
                                        "flex": 1,
                                    },
                                    {
                                        "headerName": "Zlecenia",
                                        "field": "order_count",
                                        "width": 110,
                                    },
                                    {"headerName": "Km", "field": "distance_km", "width": 90},
                                    {"headerName": "Status", "field": "route_status_pl"},
                                ],
                                "rowData": [
                                    {
                                        "vehicle_id": r.vehicle_id,
                                        "vehicle": r.vehicle_code,
                                        "drop_summary": r.drop_summary or "—",
                                        "order_count": r.order_count,
                                        "distance_km": r.distance_km,
                                        "route_status_pl": route_status_pl(r.route_status),
                                    }
                                    for r in snap.in_transit
                                ],
                                "rowSelection": "multiple",
                                "suppressRowClickSelection": True,
                                "domLayout": "normal",
                            }
                        )
                        .classes("w-full")
                        .style("height: 180px")
                    )

                async def _complete_selected() -> None:
                    if on_complete_routes is None:
                        return
                    rows = await transit_grid.get_selected_rows()
                    if not rows:
                        ui.notify("Zaznacz co najmniej jedną trasę w drodze.", type="warning")
                        return
                    vehicle_ids = [int(r["vehicle_id"]) for r in rows if r.get("vehicle_id")]
                    if not vehicle_ids:
                        ui.notify("Brak pojazdów na zaznaczonych trasach.", type="warning")
                        return
                    await on_complete_routes(vehicle_ids)

                with ui.row().classes("cd-toolbar"):
                    complete_transit_btn = ui.button("Zrealizowane", icon="done").props(
                        "color=positive no-caps"
                    )
                complete_transit_btn.on_click(_complete_selected)
                enlarge_transit_btn.on_click(
                    attach_grid_enlarge(
                        transit_grid,
                        transit_host,
                        title="Trasy w drodze",
                        compact_height="180px",
                        toolbar_builder=lambda: ui.button(
                            "Zrealizowane",
                            icon="done",
                            on_click=_complete_selected,
                        ).props("color=positive"),
                    )
                )
            else:
                enlarge_transit_btn.set_visibility(False)
                ui.label("Brak tras oczekujących na realizację.").classes("text-sm text-gray-500")

    ui.html(
        "<div class='cd-ops-kpis'>"
        f"<div class='cd-ops-kpi'><b>{snap.total_orders}</b>"
        "<span>Wszystkie zlecenia</span></div>"
        f"<div class='cd-ops-kpi'><b>{snap.new_orders}</b>"
        "<span>Nowe</span></div>"
        f"<div class='cd-ops-kpi'><b>{snap.planned_orders}</b>"
        "<span>Zaplanowane</span></div>"
        f"<div class='cd-ops-kpi'><b>{snap.approved_orders}</b>"
        "<span>Zatwierdzone</span></div>"
        "</div>",
        sanitize=False,
    )

    with ui.element("div").classes("cd-ops-foot"):
        ui.html(
            "<div class='cd-ops-card'>"
            "<h4>Kolejka magazynowa</h4>"
            f"<div class='v'>{snap.queue_count}</div>"
            "<p>pozycji w kolejce</p>"
            "</div>",
            sanitize=False,
        )
        with ui.element("div").classes("cd-ops-card"):
            ui.html("<h4>Skróty</h4>", sanitize=False)
            with ui.row().classes("gap-1 flex-wrap ui-sans"):
                ui.button(
                    "Zlecenia",
                    on_click=lambda: ui.navigate.to("/orders"),
                ).props("flat dense color=primary no-caps")
                ui.button(
                    "Operacje",
                    on_click=lambda: ui.navigate.to("/plans"),
                ).props("flat dense color=primary no-caps")
                ui.button(
                    "Magazyn",
                    on_click=lambda: ui.navigate.to("/warehouse"),
                ).props("flat dense color=primary no-caps")
                ui.button(
                    "Raporty",
                    on_click=lambda: ui.navigate.to("/reports"),
                ).props("flat dense color=primary no-caps")
        ui.html(
            f"<div class='cd-ops-card'><h4>Ostatni import</h4><p>{import_txt}</p></div>",
            sanitize=False,
        )
