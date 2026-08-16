"""Ops Focus dashboard renderer (Magic Patterns Concept B)."""

from __future__ import annotations

import html
from collections.abc import Awaitable, Callable
from typing import Any

from nicegui import ui

from crossdock.services.dashboard import DashboardSnapshot
from crossdock.ui.layout import ops_page_header
from crossdock.ui.widgets import info_hint


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
    on_select_plan: Callable[[int], Awaitable[Any] | Any] | None = None,
    on_complete_route: Callable[[int, int, str, int], Awaitable[Any] | Any] | None = None,
) -> None:
    """Paint the Ops Focus home layout inside an already-open page_frame."""
    plan_title = snap.plan_label or "Brak planu"
    plan_sub = (
        f"status: {snap.latest_plan_status_pl or '—'}"
        if snap.latest_plan_id is not None
        else "Wygeneruj pierwszy plan w sekcji Plany."
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
    select_options = {str(run_id): label for run_id, label in snap.plan_options}

    ops_page_header(
        "Pulpit dyspozytora",
        "Import zleceń, planowanie transportów całopojazdowych, mapa tras, magazyn i raporty.",
    )

    with ui.element("div").classes("cd-ops-hero"):
        with ui.row().classes("w-full items-start justify-between flex-wrap gap-4"):
            with ui.column().classes("gap-1").style("min-width:min(100%, 28rem);flex:1;"):
                ui.label("Aktywny plan").classes("cd-ops-eyebrow")
                if select_options:
                    plan_select = ui.select(
                        options=select_options,
                        value=(
                            str(snap.latest_plan_id) if snap.latest_plan_id is not None else None
                        ),
                        label="Plan",
                    ).classes("w-full cd-ops-plan-title")

                    async def _on_plan_change(_e: Any = None) -> None:
                        raw = plan_select.value
                        if raw is None or on_select_plan is None:
                            return
                        chosen = int(raw)
                        if chosen == snap.latest_plan_id:
                            return
                        await on_select_plan(chosen)

                    plan_select.on_value_change(_on_plan_change)
                else:
                    ui.html(f"<h2 class='cd-ops-plan-title'>{plan_title_e}</h2>", sanitize=False)
                ui.html(f"<div class='cd-ops-plan-sub'>{plan_sub_e}</div>", sanitize=False)
            ui.html(pill, sanitize=False)
        with ui.element("div").classes("cd-ops-tri"):
            _status_tile(
                "Jedzie (trasy)",
                snap.riding,
                "trasy gotowe do zatwierdzenia",
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
                "Otwórz plany",
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

        with ui.element("div").classes("w-full mt-3 gap-2").style(
            "display:flex;flex-direction:column;gap:0.5rem;"
        ):
            with ui.row().classes("w-full items-center gap-2"):
                ui.label("Trasy w drodze").classes("text-sm font-medium")
                info_hint(
                    "Zatwierdzone trasy aktywnego planu — po powrocie oznacz Zrealizowane "
                    "(zlecenia dostarczone, pojazd wolny, historia zostaje)."
                )
            routes = list(snap.in_progress_routes)
            if not routes:
                ui.label("Brak tras oczekujących na realizację.").classes(
                    "text-sm text-gray-500"
                )
            else:
                route_options = {
                    str(r.vehicle_id): (
                        f"{r.vehicle_code} · {r.order_count} zleceń · "
                        f"{r.drops_summary} · {r.distance_km:.0f} km"
                    )
                    for r in routes
                }
                selected = ui.radio(route_options, value=next(iter(route_options))).props(
                    "dense"
                )
                by_id = {r.vehicle_id: r for r in routes}

                async def _on_complete_dash() -> None:
                    if on_complete_route is None:
                        return
                    raw = selected.value
                    if raw is None:
                        ui.notify("Wybierz trasę.", type="warning")
                        return
                    route = by_id.get(int(raw))
                    if route is None:
                        ui.notify("Nie znaleziono trasy.", type="warning")
                        return
                    await on_complete_route(
                        route.run_id,
                        route.vehicle_id,
                        route.vehicle_code,
                        route.order_count,
                    )

                ui.button(
                    "Zrealizowane",
                    icon="local_shipping",
                    on_click=_on_complete_dash,
                ).props("color=positive no-caps")

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
                    "Plany",
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
