"""Application pages: dashboard, orders, plans, map, reports, warehouse, system, settings.

UI texts in Polish.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from nicegui import app, run, ui

from crossdock.config import effective_planning_date, get_settings
from crossdock.distance.factory import get_distance_provider
from crossdock.distance.osrm import OsrmDistanceProvider
from crossdock.domain.models import Location, Order, Vehicle, VehicleType
from crossdock.services.app_settings import (
    editable_settings_snapshot,
    save_runtime_overrides,
)
from crossdock.services.backup import run_backup
from crossdock.services.buffering import accept_buffer_proposals, compute_buffer_proposals
from crossdock.services.dashboard import collect_dashboard
from crossdock.services.import_orders import ImportOrdersService, ImportOutcome
from crossdock.services.locations import (
    apply_coords_to_existing_orders,
    delete_location,
    list_locations,
    seed_location_coords,
    upsert_location,
)
from crossdock.services.map_arrows import segment_arrows
from crossdock.services.map_view import MapPlanView, MapViewService
from crossdock.services.orders import (
    OrderCounts,
    delete_all_orders,
    delete_orders,
    order_counts,
    update_approved_pallets,
)
from crossdock.services.plan_view import PlanView, build_plan_view, list_in_transit_routes
from crossdock.services.planning import (
    AssignmentStageResult,
    PlanningService,
    PlanSolveRequest,
    PreparedPlanResult,
    RoutingBundle,
    assemble_prepared_plan,
    build_routing_bundle,
    fetch_route_polylines,
    solve_assignment_stage,
    solve_routes_stage,
)
from crossdock.services.reports import ReportBundle, build_report, export_report_xlsx
from crossdock.services.system_status import (
    LOG_FULL_BYTES,
    LOG_PREVIEW_BYTES,
    LOG_PREVIEW_LINES,
    collect_system_status,
    read_log_file,
)
from crossdock.services.warehouse_queue import (
    dequeue_order,
    enqueue_many,
    enqueue_order,
    list_enqueue_candidates,
    list_queue,
    move_order,
    set_held,
)
from crossdock.services.warehouse_stock import warehouse_snapshot
from crossdock.storage.database import session_scope
from crossdock.storage.repositories import (
    AssignmentRepository,
    OrderRepository,
    VehicleRepository,
)
from crossdock.ui.labels import (
    PLAN_NAME_MAX_LEN,
    buffer_action_pl,
    format_plan_label,
    order_status_pl,
    plan_status_pl,
    queue_status_pl,
    route_status_pl,
)
from crossdock.ui.layout import ops_page_header, page_frame
from crossdock.ui.widgets import (
    attach_grid_enlarge,
    enlarge_grid_button,
    info_hint,
    selection_column,
)


def _active_run_id_from_storage() -> int | None:
    raw = app.storage.user.get("active_run_id")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    return None


def _set_active_run_id(run_id: int | None) -> None:
    if run_id is None:
        app.storage.user.pop("active_run_id", None)
    else:
        app.storage.user["active_run_id"] = int(run_id)


def _orders_to_grid_rows(orders: list[Order]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for order in orders:
        rows.append(
            {
                "id": order.id,
                "delivery_code": order.delivery_code,
                "delivery_name": order.delivery_location.name,
                "delivery_city": order.delivery_location.city or "",
                "delivery_date": order.delivery_date.isoformat(),
                "status": order_status_pl(order.status.value),
                "status_code": order.status.value,
                "shipments": len(order.shipments),
                "pallets": order.total_pallets if order.total_pallets is not None else "?",
                "weight_kg": (
                    round(order.total_weight_kg, 1) if order.total_weight_kg is not None else "?"
                ),
            }
        )
    return rows


def _load_orders() -> list[Order]:
    with session_scope() as session:
        return OrderRepository(session).list_all()


def _load_order_counts() -> OrderCounts:
    with session_scope() as session:
        return order_counts(session)


def _delete_orders_by_ids(order_ids: list[int], username: str) -> int:
    with session_scope() as session:
        return delete_orders(session, order_ids=order_ids, username=username)


def _delete_all_orders(username: str) -> int:
    with session_scope() as session:
        return delete_all_orders(session, username=username)


def _load_planning_context(preferred_run_id: int | None = None) -> dict[str, object]:
    with session_scope() as session:
        counts = order_counts(session)
        vehicle_repo = VehicleRepository(session)
        active_vehicles = vehicle_repo.list_active()
        available_vehicles = vehicle_repo.list_available()
        planning = PlanningService(session)
        resolved = planning.resolve_run_id(preferred_run_id)
        run = AssignmentRepository(session).get_run(resolved) if resolved is not None else None
        plans = planning.list_recent_plans(limit=30)
        busy = sum(1 for v in active_vehicles if v.is_busy)
        fleet_rows = [
            {
                "id": v.id,
                "code": v.code,
                "vehicle_type": v.vehicle_type.value,
                "is_busy": v.is_busy,
            }
            for v in sorted(active_vehicles, key=lambda x: (x.is_busy, x.code))
        ]
        return {
            "total_orders": counts.total,
            "new_orders": counts.new_status,
            "eligible_orders": counts.new_with_weight,
            "active_vehicles": len(active_vehicles),
            "available_vehicles": len(available_vehicles),
            "busy_vehicles": busy,
            "fleet_rows": fleet_rows,
            "plan_status": run.plan_status if run is not None else None,
            "latest_run_id": resolved,
            "display_name": run.display_name if run is not None else None,
            "created_at": run.created_at if run is not None else None,
            "plan_label": (
                format_plan_label(
                    run_id=run.id,
                    display_name=run.display_name,
                    plan_status=run.plan_status,
                    created_at=run.created_at,
                )
                if run is not None
                else None
            ),
            "plan_options": [(item.run_id, item.label) for item in plans],
            "total_distance_km": run.total_distance_km if run else None,
            "total_cost_eur": run.total_cost_eur if run else None,
        }


def _approve_route_job(run_id: int, vehicle_id: int, username: str) -> tuple[int, int, str]:
    with session_scope() as session:
        outcome = PlanningService(session).approve_route(
            run_id=run_id, vehicle_id=vehicle_id, username=username
        )
        return outcome.run_id, len(outcome.approved_order_ids), outcome.vehicle_code or "?"


def _unlock_route_job(run_id: int, vehicle_id: int, username: str) -> tuple[int, int, str]:
    with session_scope() as session:
        outcome = PlanningService(session).unlock_route(
            run_id=run_id, vehicle_id=vehicle_id, username=username
        )
        return outcome.run_id, len(outcome.reset_order_ids), outcome.vehicle_code or "?"


def _complete_route_job(run_id: int, vehicle_id: int, username: str) -> tuple[int, int, str]:
    with session_scope() as session:
        outcome = PlanningService(session).complete_route(
            run_id=run_id, vehicle_id=vehicle_id, username=username
        )
        return outcome.run_id, len(outcome.delivered_order_ids), outcome.vehicle_code or "?"


def _import_upload(path: Path, username: str) -> ImportOutcome:
    with session_scope() as session:
        return ImportOrdersService(session).import_path(path, username=username)


def _open_import_result_dialog(outcome: ImportOutcome) -> None:
    with (
        ui.dialog() as dialog,
        ui.card()
        .classes("p-4 gap-3")
        .style("min-width:min(92vw, 52rem);max-width:52rem;max-height:85vh;"),
    ):
        ui.label("Wynik importu").classes("text-lg font-medium")
        ui.label(
            f"Przyjęto {outcome.accepted_count} · "
            f"pominięto (już w bazie) {len(outcome.skipped)} · "
            f"błędy wierszy {len(outcome.rejected)}"
        ).classes("text-sm text-gray-700")
        if outcome.warnings:
            for warning in outcome.warnings:
                ui.label(warning).classes("text-sm text-amber-800")
        if outcome.skipped:
            ui.label("Już w systemie").classes("font-medium mt-2")
            with (
                ui.scroll_area().classes("w-full").style("max-height: 32vh"),
                ui.column().classes("w-full gap-0"),
            ):
                for item in outcome.skipped:
                    oid = (
                        f" · zlecenie #{item.existing_order_id}"
                        if item.existing_order_id is not None
                        else ""
                    )
                    ui.label(f"{item.delivery_code}{oid}").classes("text-sm")
        if outcome.rejected:
            ui.label("Błędy wierszy").classes("font-medium mt-2")
            with (
                ui.scroll_area().classes("w-full").style("max-height: 32vh"),
                ui.column().classes("w-full gap-0"),
            ):
                for err in outcome.rejected:
                    ui.label(f"Wiersz {err.row_number}: {err.message}").classes("text-sm")
        with ui.row().classes("gap-2 justify-end w-full"):
            ui.button("Zamknij", on_click=dialog.close).props("color=primary")
    dialog.open()


def _load_last_import_summary() -> str | None:
    with session_scope() as session:
        return collect_system_status(session).last_import_summary


def _load_dashboard(run_id: int | None = None):
    with session_scope() as session:
        return collect_dashboard(session, run_id=run_id)


def _load_latest_plan_view(run_id: int | None = None) -> PlanView:
    with session_scope() as session:
        return build_plan_view(session, run_id=run_id)


def _enqueue_staying_job(order_ids: list[int], username: str) -> int:
    with session_scope() as session:
        return enqueue_many(session, order_ids=order_ids, username=username)


def _prepare_plan_job(target_run_id: int | None, force_new: bool = False):
    with session_scope() as session:
        return PlanningService(session).prepare_plan_request(
            target_run_id=target_run_id,
            force_new=force_new,
        )


def _build_routing_bundle_job(assignment_stage: AssignmentStageResult, request: PlanSolveRequest):
    distance = get_distance_provider(get_settings())
    return build_routing_bundle(assignment_stage.assignment, request, distance=distance)


def _finalize_plan_job(
    request: PlanSolveRequest,
    assignment_stage: AssignmentStageResult,
    bundle: RoutingBundle,
    routing: object,
) -> PreparedPlanResult:
    """OSRM /route (if enabled) + assemble persistable plan — ``run.io_bound``."""
    settings = get_settings()
    polylines: dict[int, list[tuple[float, float]]] | None = None
    if settings.use_osrm:
        provider = get_distance_provider(settings)
        if isinstance(provider, OsrmDistanceProvider):
            polylines = fetch_route_polylines(
                routing,  # type: ignore[arg-type]
                request,
                bundle,
                route_fetcher=provider.route_polyline,
            )
    return assemble_prepared_plan(
        request,
        assignment_stage.assignment,
        bundle,
        routing,  # type: ignore[arg-type]
        polylines_by_vehicle=polylines,
    )


def _persist_plan_job(
    prepared: PreparedPlanResult, username: str
) -> tuple[int, str, int, int, int, list[str]]:
    with session_scope() as session:
        outcome = PlanningService(session).persist_prepared_plan(prepared, username=username)
    plan = outcome.plan
    return (
        outcome.run_id,
        plan.status,
        len(outcome.planned_order_ids),
        len(plan.assignment.unassigned_order_ids),
        len(plan.routing.unrouted_order_ids),
        list(plan.warnings),
    )


def _save_planning_date_job(iso: str | None, username: str) -> str:
    with session_scope() as session:
        save_runtime_overrides({"planning_date": iso or None}, session=session, username=username)
    return effective_planning_date().isoformat()


def _advance_planning_date_job(username: str) -> str:
    nxt = effective_planning_date() + timedelta(days=1)
    with session_scope() as session:
        save_runtime_overrides(
            {"planning_date": nxt.isoformat()}, session=session, username=username
        )
    return nxt.isoformat()


def _approve_plan_job(run_id: int, username: str) -> tuple[int, int]:
    with session_scope() as session:
        outcome = PlanningService(session).approve_plan(run_id=run_id, username=username)
    return outcome.run_id, len(outcome.approved_order_ids)


def _unlock_plan_job(run_id: int, username: str) -> tuple[int, int]:
    with session_scope() as session:
        outcome = PlanningService(session).unlock_plan(run_id=run_id, username=username)
    return outcome.run_id, len(outcome.reset_order_ids)


def _delete_plan_job(run_id: int, username: str) -> tuple[int, int, int | None]:
    with session_scope() as session:
        outcome = PlanningService(session).delete_plan(run_id=run_id, username=username)
        remaining = PlanningService(session).resolve_run_id(None)
    return outcome.run_id, len(outcome.reset_order_ids), remaining


def _rename_plan_job(run_id: int, display_name: str, username: str) -> str | None:
    with session_scope() as session:
        return PlanningService(session).rename_plan(
            run_id=run_id, display_name=display_name, username=username
        )


def _create_empty_plan_job(username: str) -> int:
    with session_scope() as session:
        return PlanningService(session).create_empty_plan(username=username)


def _update_pallets_job(order_id: int, total: int, username: str):
    with session_scope() as session:
        return update_approved_pallets(
            session, order_id=order_id, total_pallets=total, username=username
        )


@ui.page("/")
async def dashboard_page() -> None:
    with page_frame("Pulpit"):
        host = ui.column().classes("w-full gap-4")
        username = app.storage.user.get("username", "unknown")

        async def refresh_dashboard() -> None:
            preferred = _active_run_id_from_storage()
            snap = await run.io_bound(_load_dashboard, preferred)
            _set_active_run_id(snap.latest_plan_id)

            async def on_enqueue_staying() -> None:
                ids = list(snap.staying_order_ids)
                if not ids:
                    ui.notify("Brak zleceń do dodania do kolejki.", type="info")
                    return
                added = await run.io_bound(_enqueue_staying_job, ids, username)
                ui.notify(
                    f"Dodano do kolejki: {added}."
                    if added
                    else "Nic nie dodano (już w kolejce lub inny status).",
                    type="positive" if added else "info",
                )

            def open_map() -> None:
                if snap.latest_plan_id is None:
                    ui.navigate.to("/map")
                else:
                    ui.navigate.to(f"/map?run_id={snap.latest_plan_id}")

            async def on_select_plan(run_id: int) -> None:
                if run_id == snap.latest_plan_id:
                    return
                _set_active_run_id(run_id)
                await refresh_dashboard()

            async def on_complete_routes(vehicle_ids: list[int]) -> None:
                run_id = snap.latest_plan_id
                if run_id is None:
                    ui.notify("Brak aktywnego planu.", type="warning")
                    return
                results: list[tuple[int, int, str]] = []
                errors: list[str] = []
                for vehicle_id in vehicle_ids:
                    try:
                        results.append(
                            await run.io_bound(
                                _complete_route_job, int(run_id), int(vehicle_id), username
                            )
                        )
                    except Exception as exc:
                        errors.append(f"pojazd {vehicle_id}: {exc}")
                if not results:
                    ui.notify(
                        "Nie udało się oznaczyć żadnej trasy: " + "; ".join(errors),
                        type="negative",
                    )
                    return
                if len(results) == 1:
                    rid, n_orders, code = results[0]
                    ui.notify(
                        f"Zrealizowano trasę {code} (plan #{rid}, {n_orders} zleceń). Auto wolne.",
                        type="positive",
                    )
                else:
                    display = ", ".join(code for _, _, code in results[:5])
                    if len(results) > 5:
                        display += "..."
                    ui.notify(
                        f"Zrealizowano {len(results)} tras: {display}.",
                        type="positive",
                    )
                if errors:
                    ui.notify(
                        "Część tras nie została oznaczona jako zrealizowana: "
                        + "; ".join(errors[:3]),
                        type="warning",
                    )
                await refresh_dashboard()

            host.clear()
            with host:
                from crossdock.ui.ops_dashboard import render_ops_focus_dashboard

                render_ops_focus_dashboard(
                    snap,
                    on_enqueue_staying=on_enqueue_staying,
                    open_map=open_map,
                    on_select_plan=on_select_plan,
                    on_complete_routes=on_complete_routes,
                )

        await refresh_dashboard()


@ui.page("/orders")
async def orders_page() -> None:
    username = app.storage.user.get("username", "unknown")

    with page_frame("Zlecenia"):
        ops_page_header(
            "Zlecenia",
            "Import z Excela i przegląd zleceń.",
        )
        session_import = app.storage.user.get("last_import")
        if isinstance(session_import, dict):
            tone = "cd-ops-hero" if int(session_import.get("rejected", 0)) == 0 else "cd-ops-panel"
            with ui.element("div").classes(f"w-full {tone}"):
                ui.label(
                    f"Ostatni import (sesja): przyjęto {session_import.get('accepted', 0)}, "
                    f"pominięto {session_import.get('skipped', 0)}, "
                    f"odrzucono {session_import.get('rejected', 0)} "
                    f"({session_import.get('at', '')})."
                ).classes("text-sm text-gray-700")
        else:
            last_import = await run.io_bound(_load_last_import_summary)
            if last_import:
                with ui.element("div").classes("w-full cd-ops-hero"):
                    ui.label(f"Ostatni import: {last_import}").classes("text-sm text-gray-700")

        with ui.element("div").classes("cd-ops-panel w-full gap-3"):
            status_label = ui.label("").classes("text-sm text-gray-700 font-medium")

            with ui.row().classes("cd-toolbar w-full"):
                refresh_btn = ui.button("Odśwież", icon="refresh").props("outline")
                delete_selected_btn = ui.button("Usuń zaznaczone", icon="delete").props(
                    "outline color=negative"
                )
                delete_all_btn = ui.button("Usuń wszystkie", icon="delete_sweep").props(
                    "outline color=negative"
                )
                pallets_btn = (
                    ui.button("Zmień palety", icon="pallet").props("outline").classes("hidden")
                )
                pallets_btn.disable()
                info_hint(
                    "Gdy baza jest pusta, zaimportuj plik Excel, aby rozpocząć planowanie. "
                    "Zlecenia o istniejącym kodzie dostawy są pomijane. Usuń zaznaczone w tabeli. "
                    "Zmień palety: dostępne po zatwierdzeniu planu; "
                    "zaznacz jedno zlecenie zatwierdzone."
                )
                upload = (
                    ui.upload(
                        on_upload=lambda e: handle_upload(e),
                        auto_upload=True,
                        max_files=1,
                    )
                    .props('accept=".xlsx,.xls"')
                    .classes("hidden")
                )
                ui.button(
                    "Importuj z Excela",
                    icon="upload_file",
                    on_click=lambda: upload.run_method("pickFiles"),
                ).props("color=primary")
                info_hint(
                    "Importuj raport Excel z TMS (nagłówek w trzecim wierszu arkusza). "
                    "Kolumny mapuje konfiguracja importu."
                )
                enlarge_orders_btn = ui.button("Powiększ", icon="open_in_full").props(
                    "flat dense no-caps"
                )

        orders_host = ui.element("div").classes("cd-grid-host")
        with orders_host:
            grid = (
                ui.aggrid(
                    {
                        "columnDefs": [
                            selection_column(multiple=True),
                            {"headerName": "ID", "field": "id", "width": 70, "sortable": True},
                            {"headerName": "Kod dostawy", "field": "delivery_code", "filter": True},
                            {"headerName": "Odbiorca", "field": "delivery_name", "filter": True},
                            {"headerName": "Miasto", "field": "delivery_city", "filter": True},
                            {
                                "headerName": "Termin",
                                "field": "delivery_date",
                                "filter": True,
                                "sortable": True,
                            },
                            {"headerName": "Status", "field": "status", "filter": True},
                            {"headerName": "Przesyłki", "field": "shipments", "sortable": True},
                            {"headerName": "Palety", "field": "pallets", "sortable": True},
                            {"headerName": "Waga [kg]", "field": "weight_kg", "sortable": True},
                        ],
                        "rowData": [],
                        "defaultColDef": {"sortable": True, "resizable": True},
                        "rowSelection": "multiple",
                        "suppressRowClickSelection": True,
                        "domLayout": "normal",
                    }
                )
                .classes("w-full")
                .style("height: 420px")
            )
        enlarge_orders_btn.on_click(
            attach_grid_enlarge(
                grid,
                orders_host,
                title="Zlecenia",
                compact_height="420px",
            )
        )

        async def sync_pallets_button() -> None:
            selected = await grid.get_selected_rows()
            can_edit = len(selected) == 1 and str(selected[0].get("status_code", "")) == "approved"
            if can_edit:
                pallets_btn.enable()
            else:
                pallets_btn.disable()

        async def sync_toolbar(counts: OrderCounts) -> None:
            status_label.set_text(
                f"Zlecenia w bazie: {counts.total} "
                f"(status „nowe”: {counts.new_status}, z wagą: {counts.new_with_weight})"
            )
            if counts.total == 0:
                delete_all_btn.disable()
            else:
                delete_all_btn.enable()
            await sync_pallets_button()

        async def refresh_grid() -> None:
            orders = await run.io_bound(_load_orders)
            counts = await run.io_bound(_load_order_counts)
            grid.options["rowData"] = _orders_to_grid_rows(orders)
            grid.update()
            await sync_toolbar(counts)

        async def handle_upload(e: ui.events.UploadEventArguments) -> None:
            settings = get_settings()
            content = await e.file.read()
            max_bytes = settings.upload_max_mb * 1024 * 1024
            if len(content) > max_bytes:
                ui.notify(
                    f"Plik za duży (limit {settings.upload_max_mb} MB).",
                    type="negative",
                )
                return
            suffix = Path(e.file.name or "upload.xlsx").suffix or ".xlsx"

            def _write_and_import() -> ImportOutcome:
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    tmp.write(content)
                    tmp_path = Path(tmp.name)
                try:
                    return _import_upload(tmp_path, username)
                finally:
                    tmp_path.unlink(missing_ok=True)

            outcome = await run.io_bound(_write_and_import)
            skipped_n = len(outcome.skipped)
            rejected_n = len(outcome.rejected)
            app.storage.user["last_import"] = {
                "accepted": outcome.accepted_count,
                "rejected": rejected_n,
                "skipped": skipped_n,
                "at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            toast_type = "positive" if rejected_n == 0 and skipped_n == 0 else "warning"
            ui.notify(
                f"Przyjęto {outcome.accepted_count}, pominięto {skipped_n}, błędy {rejected_n}",
                type=toast_type,
            )
            if skipped_n > 0 or rejected_n > 0 or outcome.warnings:
                _open_import_result_dialog(outcome)
            await refresh_grid()

        async def on_delete_selected() -> None:
            selected = await grid.get_selected_rows()
            if not selected:
                ui.notify("Zaznacz co najmniej jedno zlecenie.", type="warning")
                return
            ids = [int(row["id"]) for row in selected]
            deleted = await run.io_bound(_delete_orders_by_ids, ids, username)
            ui.notify(f"Usunięto {deleted} zleceń.", type="positive")
            await refresh_grid()

        async def on_delete_all() -> None:
            counts = await run.io_bound(_load_order_counts)
            if counts.total == 0:
                ui.notify("Baza zleceń jest już pusta.", type="info")
                return
            with ui.dialog() as dialog, ui.card().classes("p-4 gap-3"):
                ui.label(f"Czy na pewno usunąć wszystkie {counts.total} zleceń?").classes(
                    "font-medium"
                )
                with ui.row().classes("gap-2 justify-end w-full"):
                    ui.button("Anuluj", on_click=dialog.close).props("flat")

                    async def confirm() -> None:
                        dialog.close()
                        deleted = await run.io_bound(_delete_all_orders, username)
                        ui.notify(f"Usunięto {deleted} zleceń.", type="positive")
                        await refresh_grid()

                    ui.button("Usuń wszystkie", on_click=confirm).props("color=negative")
            dialog.open()

        async def on_edit_pallets() -> None:
            selected = await grid.get_selected_rows()
            if not selected or len(selected) != 1:
                ui.notify("Zaznacz dokładnie jedno zlecenie zatwierdzone.", type="warning")
                return
            row = selected[0]
            if str(row.get("status_code")) != "approved":
                ui.notify(
                    "Edycja palet tylko dla zleceń zatwierdzonych.",
                    type="warning",
                )
                return
            order_id = int(row["id"])
            current = row.get("pallets")
            default_val = int(current) if isinstance(current, (int, float)) else 0
            with ui.dialog() as dialog, ui.card().classes("p-4 gap-3 min-w-[280px]"):
                ui.label(f"Palety — {row['delivery_code']}").classes("font-medium")
                pallets_in = ui.number("Liczba palet", value=default_val, min=0, precision=0)

                async def save_pallets() -> None:
                    try:
                        result = await run.io_bound(
                            _update_pallets_job,
                            order_id,
                            int(pallets_in.value or 0),
                            username,
                        )
                    except Exception as exc:
                        ui.notify(str(exc), type="negative")
                        return
                    dialog.close()
                    if result.warning:
                        ui.notify(
                            f"Zapisano ({result.old_total} → {result.new_total}). {result.warning}",
                            type="warning",
                        )
                    else:
                        ui.notify(
                            f"Zapisano palety: {result.old_total} → {result.new_total}.",
                            type="positive",
                        )
                    await refresh_grid()

                with ui.row().classes("gap-2 justify-end w-full"):
                    ui.button("Anuluj", on_click=dialog.close).props("flat")
                    ui.button("Zapisz", on_click=save_pallets).props("color=primary")
            dialog.open()

        refresh_btn.on_click(refresh_grid)
        delete_selected_btn.on_click(on_delete_selected)
        delete_all_btn.on_click(on_delete_all)
        pallets_btn.on_click(on_edit_pallets)
        grid.on("selectionChanged", lambda _e: sync_pallets_button())
        await refresh_grid()


@ui.page("/plans")
async def plans_page() -> None:
    username = app.storage.user.get("username", "unknown")
    settings = get_settings()
    with page_frame("Plany"):
        ops_page_header(
            "Plany FTL",
            "FTL (full truckload) — transporty całopojazdowe. "
            "Pełne auta wyjeżdżają, słabe czekają na dopełnienie. "
            "Wyjazd ok. 2 dni przed terminem u odbiorcy. "
            f"Maks. {settings.max_drops_per_route} punktów rozładunku / trasę · "
            f"{settings.cost_per_km:.2f} €/km. "
            "Zatwierdzaj pełne trasy — słabe zostają w magazynie na kolejny dzień.",
        )

        ctx = await run.io_bound(_load_planning_context, _active_run_id_from_storage())
        active_id = ctx.get("latest_run_id")
        _set_active_run_id(int(active_id) if isinstance(active_id, int) else None)
        staying_ids: list[int] = []
        updating_plan_select = False

        def _plan_chip(caption: str, *, muted: bool = False) -> tuple[ui.element, ui.label]:
            cls = "cd-plan-chip cd-plan-chip-muted" if muted else "cd-plan-chip"
            wrap = ui.element("div").classes(cls)
            with wrap:
                if caption:
                    ui.label(caption).classes("cd-plan-chip-k")
                value = ui.label("—").classes("cd-plan-chip-v")
            return wrap, value

        with ui.element("div").classes("cd-plan-meta"):
            _, chip_orders = _plan_chip("Zlecenia w bazie")
            _, chip_eligible = _plan_chip("Do planowania")
            _, chip_free = _plan_chip("Wolne pojazdy")
            _, chip_busy = _plan_chip("Zajęte")
            plan_wrap, chip_plan = _plan_chip("Plan")
            empty_wrap, chip_empty = _plan_chip("", muted=True)
            chip_empty.set_text("Brak planu — wygeneruj plan po imporcie zleceń.")
            riding_wrap, chip_riding = _plan_chip("Jedzie")
            staying_wrap, chip_staying = _plan_chip("Zostaje")
            attention_wrap, chip_attention = _plan_chip("Wymaga uwagi")
            km_wrap, chip_km = _plan_chip("Km")
            cost_wrap, chip_cost = _plan_chip("Koszt")
            plan_wrap.set_visibility(False)
            riding_wrap.set_visibility(False)
            staying_wrap.set_visibility(False)
            attention_wrap.set_visibility(False)
            km_wrap.set_visibility(False)
            cost_wrap.set_visibility(False)

        with ui.element("div").classes("cd-ops-panel w-full"):
            with ui.row().classes("cd-toolbar w-full"):
                plan_select = (
                    ui.select(
                        options={},
                        value=None,
                        label="Plan",
                    )
                    .classes("cd-plan-select")
                    .props("options-dense popup-content-class=cd-plan-select-popup")
                )
                rename_btn = ui.button("Nazwa", icon="edit").props("outline")
                new_plan_btn = ui.button("Nowy plan", icon="note_add").props("outline")
                refresh_btn = ui.button("Odśwież", icon="refresh").props("outline")
                generate_btn = ui.button("Generuj plan", icon="auto_awesome").props("color=primary")
                approve_btn = ui.button("Zatwierdź pełne trasy", icon="done_all").props(
                    "color=positive"
                )
                approve_route_btn = ui.button("Zatwierdź trasę", icon="check_circle").props(
                    "color=positive outline"
                )
                complete_route_btn = ui.button("Zrealizowane", icon="done").props("color=positive")
                unlock_route_btn = ui.button("Odblokuj trasę", icon="lock_open").props("outline")
                unlock_btn = ui.button("Odblokuj cały plan", icon="restart_alt").props("outline")
                delete_plan_btn = ui.button("Usuń plan", icon="delete").props(
                    "outline color=negative"
                )
                map_btn = ui.button("Pokaż na mapie", icon="map").props("outline")
            sim_day = effective_planning_date(settings)
            with ui.row().classes("cd-toolbar w-full items-end"):
                planning_date_in = (
                    ui.input(
                        "Dzień planowania",
                        value=sim_day.isoformat(),
                    )
                    .props("type=date")
                    .classes("w-48")
                )
                sim_label = ui.label(
                    "symulacja" if settings.planning_date is not None else "data kalendarzowa"
                ).classes("text-sm text-gray-600")

                async def on_apply_planning_date() -> None:
                    raw = str(planning_date_in.value or "").strip()
                    iso = raw or None
                    applied = await run.io_bound(_save_planning_date_job, iso, username)
                    planning_date_in.value = applied
                    sim_label.set_text("symulacja" if iso else "data kalendarzowa")
                    ui.notify(f"Dzień planowania: {applied}", type="positive")
                    await refresh_plan_view()

                async def on_next_planning_day() -> None:
                    applied = await run.io_bound(_advance_planning_date_job, username)
                    planning_date_in.value = applied
                    sim_label.set_text("symulacja")
                    ui.notify(f"Następny dzień: {applied}", type="positive")
                    await refresh_plan_view()

                ui.button("Zastosuj dzień", on_click=on_apply_planning_date).props("outline")
                ui.button("Następny dzień", icon="skip_next", on_click=on_next_planning_day).props(
                    "outline"
                )
            blocker_label = ui.label("").classes("text-sm text-red-700")
            blocker_label.set_visibility(False)
            result_label = ui.label("").classes("text-sm text-gray-600")
            result_label.set_visibility(False)
            warn_box = ui.column().classes("w-full gap-1")
            gen_dialog = ui.dialog().props("persistent")
            with gen_dialog, ui.card().classes("w-[28rem] p-4 gap-3"):
                ui.label("Generowanie planu FTL").classes("text-lg font-medium")
                gen_progress = ui.linear_progress(value=0, show_value=False).props(
                    "instant-feedback size=20px color=primary"
                )
                gen_stage = ui.label("Przygotowanie danych").classes("text-sm text-gray-700")
                gen_error = ui.label("").classes("text-sm text-red-700")
                gen_error.set_visibility(False)
                gen_close_btn = ui.button("Zamknij", on_click=gen_dialog.close).props("outline")
                gen_close_btn.set_visibility(False)

            def _bump_generate_progress() -> None:
                current = float(gen_progress.value or 0.2)
                if current < 0.9:
                    gen_progress.set_value(min(0.9, round(current + 0.02, 3)))

            gen_tick = ui.timer(0.4, _bump_generate_progress, active=False)

        with ui.element("div").classes("cd-fleet-board w-full"):
            with ui.element("div").classes("cd-fleet-col"):
                ui.html(
                    "<div class='cd-fleet-col-head'><h3>Flota</h3></div>",
                    sanitize=False,
                )
                fleet_list = ui.column().classes("cd-fleet-list w-full gap-0")

            with ui.element("div").classes("cd-routes-col"):
                with ui.element("div").classes("cd-routes-col-head"):
                    ui.html("<h3>Trasy</h3>", sanitize=False)
                    enlarge_routes_btn = ui.button("Powiększ", icon="open_in_full").props(
                        "flat dense no-caps"
                    )
                with (
                    ui.element("div")
                    .classes("p-3 w-full gap-2")
                    .style("display:flex;flex-direction:column;gap:0.75rem;")
                ):
                    routes_host = ui.element("div").classes("cd-grid-host")
                    with routes_host:
                        routes_grid = (
                            ui.aggrid(
                                {
                                    "columnDefs": [
                                        selection_column(multiple=True),
                                        {
                                            "headerName": "ID poj.",
                                            "field": "vehicle_id",
                                            "width": 90,
                                        },
                                        {
                                            "headerName": "Pojazd",
                                            "field": "vehicle",
                                            "filter": True,
                                        },
                                        {
                                            "headerName": "Status",
                                            "field": "route_status_pl",
                                            "filter": True,
                                        },
                                        {
                                            "headerName": "Do wysłania",
                                            "field": "deadline_label",
                                            "sortable": True,
                                            "width": 118,
                                        },
                                        {
                                            "headerName": "Punkty rozładunku",
                                            "field": "drop_count",
                                            "sortable": True,
                                        },
                                        {
                                            "headerName": "Km",
                                            "field": "distance_km",
                                            "sortable": True,
                                        },
                                        {
                                            "headerName": "Koszt €",
                                            "field": "cost_eur",
                                            "sortable": True,
                                        },
                                        {
                                            "headerName": "Zapełnienie wag. %",
                                            "field": "weight_fill_pct",
                                            "sortable": True,
                                            "width": 140,
                                        },
                                        {
                                            "headerName": "Decyzja",
                                            "field": "sla_label",
                                            "filter": True,
                                            "flex": 1,
                                        },
                                    ],
                                    "rowData": [],
                                    "rowSelection": "multiple",
                                    "suppressRowClickSelection": True,
                                    "defaultColDef": {"sortable": True, "resizable": True},
                                    "domLayout": "normal",
                                    "rowClassRules": {
                                        "cd-row-approved": "data.route_status === 'approved'",
                                        "cd-row-completed": "data.route_status === 'completed'",
                                        "cd-row-proposed": "data.route_status === 'proposed'",
                                        "cd-row-lowfill": "data.below_min_fill === true",
                                    },
                                }
                            )
                            .classes("w-full")
                            .style("height: 200px")
                        )
                    fill_warn_label = ui.label("").classes("text-sm text-amber-800")
                    fill_warn_label.set_visibility(False)
                    route_action_dialog = ui.dialog().classes("cd-enlarge-dialog")
                    with route_action_dialog, ui.card().classes("cd-enlarge-card"):
                        with ui.row().classes(
                            "cd-enlarge-head w-full items-center justify-between"
                        ):
                            ui.label("Trasy").classes("cd-enlarge-title")
                            ui.button(
                                "Zamknij", icon="close", on_click=route_action_dialog.close
                            ).props("flat no-caps")
                        with ui.row().classes("cd-toolbar w-full"):
                            ui.button(
                                "Zatwierdź trasę",
                                icon="check_circle",
                                on_click=lambda: on_approve_route(),
                            ).props("color=positive outline")
                            ui.button(
                                "Zrealizowane",
                                icon="done",
                                on_click=lambda: on_complete_route(),
                            ).props("color=positive")
                            ui.button(
                                "Odblokuj trasę",
                                icon="lock_open",
                                on_click=lambda: on_unlock_route(),
                            ).props("outline")
                        enlarge_route_host = ui.element("div").classes("cd-enlarge-host")

                    def open_route_enlarge() -> None:
                        routes_grid.move(enlarge_route_host)
                        routes_grid.style("height: calc(85vh - 7.5rem); width: 100%")
                        route_action_dialog.open()

                    enlarge_routes_btn.on_click(open_route_enlarge)
                    route_action_dialog.on(
                        "hide",
                        lambda *_args: (
                            routes_grid.move(routes_host),
                            routes_grid.style("height: 200px; width: 100%"),
                        ),
                    )

                    riding_cols = [
                        {"headerName": "Pojazd", "field": "vehicle", "filter": True},
                        {
                            "headerName": "Kolejność",
                            "field": "sequence",
                            "sortable": True,
                            "width": 110,
                        },
                        {"headerName": "Punkt rozładunku", "field": "drop_key", "filter": True},
                        {"headerName": "Kod dostawy", "field": "delivery_code", "filter": True},
                        {"headerName": "ID", "field": "order_id", "sortable": True, "width": 80},
                        {"headerName": "Waga [kg]", "field": "weight_kg", "sortable": True},
                        {"headerName": "Zapełnienie", "field": "fill_pct"},
                        {"headerName": "SLA", "field": "sla", "filter": True},
                    ]
                    stay_cols = [
                        {"headerName": "Kod dostawy", "field": "delivery_code", "filter": True},
                        {"headerName": "ID", "field": "order_id", "sortable": True, "width": 80},
                        {"headerName": "Waga [kg]", "field": "weight_kg", "sortable": True},
                        {"headerName": "SLA", "field": "sla", "filter": True},
                        {"headerName": "Powód", "field": "reason", "flex": 1},
                    ]

                    with ui.tabs().classes("w-full") as tabs:
                        tab_riding = ui.tab("Jedzie")
                        tab_staying = ui.tab("Zostaje w magazynie")
                        tab_attention = ui.tab("Wymaga uwagi")
                    with ui.tab_panels(tabs, value=tab_riding).classes("w-full"):
                        with ui.tab_panel(tab_riding):
                            with ui.row().classes("cd-tab-tools"):
                                info_hint("Zlecenia przypisane do tras — jadą w tym planie.")
                                enlarge_riding_btn = ui.button(
                                    "Powiększ", icon="open_in_full"
                                ).props("flat dense no-caps")
                            riding_host = ui.element("div").classes("cd-grid-host")
                            with riding_host:
                                riding_grid = (
                                    ui.aggrid(
                                        {
                                            "columnDefs": riding_cols,
                                            "rowData": [],
                                            "defaultColDef": {
                                                "sortable": True,
                                                "resizable": True,
                                            },
                                            "domLayout": "normal",
                                        }
                                    )
                                    .classes("w-full")
                                    .style("height: 300px")
                                )
                            enlarge_riding_btn.on_click(
                                attach_grid_enlarge(
                                    riding_grid,
                                    riding_host,
                                    title="Jedzie",
                                    compact_height="300px",
                                )
                            )
                        with ui.tab_panel(tab_staying):
                            with ui.row().classes("cd-tab-tools"):
                                info_hint(
                                    "Zlecenia bez miejsca w flocie oraz słabe auta czekające "
                                    "na dopełnienie (ten sam odbiorca / pełniejsza naczepa)."
                                )
                                enlarge_staying_btn = ui.button(
                                    "Powiększ", icon="open_in_full"
                                ).props("flat dense no-caps")
                            with ui.row().classes("cd-toolbar w-full mb-1"):
                                enqueue_staying_btn = ui.button(
                                    "Dodaj zostające do kolejki magazynowej",
                                    icon="playlist_add",
                                ).props("color=primary")
                                staying_empty = ui.label("Brak zleceń w tej kategorii.").classes(
                                    "text-sm text-gray-500"
                                )
                            staying_host = ui.element("div").classes("cd-grid-host")
                            with staying_host:
                                staying_grid = (
                                    ui.aggrid(
                                        {
                                            "columnDefs": stay_cols,
                                            "rowData": [],
                                            "defaultColDef": {
                                                "sortable": True,
                                                "resizable": True,
                                            },
                                            "domLayout": "normal",
                                        }
                                    )
                                    .classes("w-full")
                                    .style("height: 260px")
                                )
                            enlarge_staying_btn.on_click(
                                attach_grid_enlarge(
                                    staying_grid,
                                    staying_host,
                                    title="Zostaje w magazynie",
                                    compact_height="260px",
                                )
                            )
                        with ui.tab_panel(tab_attention):
                            with ui.row().classes("cd-tab-tools"):
                                info_hint(
                                    "Brak trasy: uzupełnij współrzędne w Ustawieniach, "
                                    "zmniejsz liczbę punktów rozładunku albo wygeneruj "
                                    "plan ponownie."
                                )
                                enlarge_attention_btn = ui.button(
                                    "Powiększ", icon="open_in_full"
                                ).props("flat dense no-caps")
                            attention_empty = ui.label("Brak zleceń w tej kategorii.").classes(
                                "text-sm text-gray-500"
                            )
                            attention_host = ui.element("div").classes("cd-grid-host")
                            with attention_host:
                                attention_grid = (
                                    ui.aggrid(
                                        {
                                            "columnDefs": stay_cols,
                                            "rowData": [],
                                            "defaultColDef": {
                                                "sortable": True,
                                                "resizable": True,
                                            },
                                            "domLayout": "normal",
                                        }
                                    )
                                    .classes("w-full")
                                    .style("height: 260px")
                                )
                            enlarge_attention_btn.on_click(
                                attach_grid_enlarge(
                                    attention_grid,
                                    attention_host,
                                    title="Wymaga uwagi",
                                    compact_height="260px",
                                )
                            )

        async def sync_planning_state(ctx_now: dict[str, object], result_text: str = "") -> None:
            nonlocal updating_plan_select
            fleet_list.clear()
            with fleet_list:
                rows = list(ctx_now.get("fleet_rows") or [])
                if not rows:
                    ui.label("Brak aktywnych pojazdów.").classes("text-sm text-gray-500 p-3")
                for row in rows:
                    busy = bool(row.get("is_busy"))
                    row_cls = (
                        "cd-fleet-row cd-fleet-row-busy"
                        if busy
                        else "cd-fleet-row cd-fleet-row-free"
                    )
                    badge_cls = "cd-badge-busy" if busy else "cd-badge-free"
                    badge_txt = "zajęty" if busy else "wolny"
                    with ui.element("div").classes(row_cls):
                        with ui.column().classes("gap-0"):
                            ui.label(str(row.get("code", ""))).classes(
                                "text-sm font-semibold"
                            ).style("color: var(--cd-heading)")
                            ui.label(str(row.get("vehicle_type", ""))).classes(
                                "text-xs text-gray-500"
                            )
                        ui.html(
                            f"<span class='{badge_cls}'>{badge_txt}</span>",
                            sanitize=False,
                        )
            chip_orders.set_text(str(ctx_now["total_orders"]))
            chip_eligible.set_text(str(ctx_now["eligible_orders"]))
            chip_free.set_text(str(ctx_now["available_vehicles"]))
            chip_busy.set_text(str(ctx_now["busy_vehicles"]))
            run_id = ctx_now.get("latest_run_id")
            if run_id is None:
                plan_wrap.set_visibility(False)
                empty_wrap.set_visibility(True)
                riding_wrap.set_visibility(False)
                staying_wrap.set_visibility(False)
                attention_wrap.set_visibility(False)
                km_wrap.set_visibility(False)
                cost_wrap.set_visibility(False)
            else:
                empty_wrap.set_visibility(False)
                plan_wrap.set_visibility(True)
                chip_plan.set_text(str(ctx_now.get("plan_label") or f"Plan #{run_id}"))
            plan_status = ctx_now.get("plan_status")
            options = {
                str(item[0]): str(item[1])
                for item in (ctx_now.get("plan_options") or [])  # type: ignore[union-attr]
            }
            updating_plan_select = True
            plan_select.set_options(options, value=str(run_id) if run_id is not None else None)
            updating_plan_select = False
            blockers: list[str] = []
            can_generate = True
            if int(ctx_now["eligible_orders"]) == 0:  # type: ignore[arg-type]
                blockers.append("brak zleceń „nowe” z wagą — wgraj Excel na Zleceniach")
                can_generate = False
            if int(ctx_now["available_vehicles"]) == 0:  # type: ignore[arg-type]
                blockers.append("brak wolnych pojazdów — odblokuj trasę lub dodaj flotę")
                can_generate = False
            if blockers and not can_generate:
                blocker_label.set_text("Nie można generować: " + "; ".join(blockers) + ".")
                blocker_label.set_visibility(True)
                generate_btn.disable()
            else:
                blocker_label.set_text("")
                blocker_label.set_visibility(False)
                generate_btn.enable()
            has_run = ctx_now.get("latest_run_id") is not None
            if has_run and plan_status in {"draft", "partial"}:
                approve_btn.enable()
                approve_route_btn.enable()
            else:
                approve_btn.disable()
                approve_route_btn.disable()
            if has_run:
                unlock_route_btn.enable()
                complete_route_btn.enable()
                unlock_btn.enable()
                delete_plan_btn.enable()
                map_btn.enable()
                rename_btn.enable()
            else:
                unlock_route_btn.disable()
                complete_route_btn.disable()
                unlock_btn.disable()
                delete_plan_btn.disable()
                map_btn.disable()
                rename_btn.disable()
            if result_text:
                result_label.set_text(result_text)
                result_label.set_visibility(True)

        async def refresh_plan_view() -> None:
            nonlocal ctx, staying_ids
            preferred = _active_run_id_from_storage()
            ctx = await run.io_bound(_load_planning_context, preferred)
            resolved = ctx.get("latest_run_id")
            _set_active_run_id(int(resolved) if isinstance(resolved, int) else None)
            view = await run.io_bound(
                _load_latest_plan_view,
                int(resolved) if isinstance(resolved, int) else None,
            )
            if view.summary is None:
                staying_ids = []
                enqueue_staying_btn.disable()
                empty_wrap.set_visibility(True)
                plan_wrap.set_visibility(False)
                riding_wrap.set_visibility(False)
                staying_wrap.set_visibility(False)
                attention_wrap.set_visibility(False)
                km_wrap.set_visibility(False)
                cost_wrap.set_visibility(False)
            else:
                staying_ids = list(view.staying_order_ids)
                if staying_ids:
                    enqueue_staying_btn.enable()
                else:
                    enqueue_staying_btn.disable()
                empty_wrap.set_visibility(False)
                plan_wrap.set_visibility(True)
                chip_plan.set_text(view.summary.label)
                riding_wrap.set_visibility(True)
                staying_wrap.set_visibility(True)
                attention_wrap.set_visibility(True)
                chip_riding.set_text(str(view.summary.riding))
                chip_staying.set_text(str(view.summary.staying))
                chip_attention.set_text(str(view.summary.attention))
                if view.summary.total_distance_km is not None:
                    km_wrap.set_visibility(True)
                    chip_km.set_text(f"{view.summary.total_distance_km:.0f}")
                else:
                    km_wrap.set_visibility(False)
                if view.summary.total_cost_eur is not None:
                    cost_wrap.set_visibility(True)
                    chip_cost.set_text(f"{view.summary.total_cost_eur:.0f} €")
                else:
                    cost_wrap.set_visibility(False)
            routes_grid.options["rowData"] = view.routes
            routes_grid.update()
            hold_n = sum(1 for row in view.routes if row.get("disposition") == "hold")
            overdue_n = sum(
                1
                for row in view.routes
                if isinstance(row.get("min_slack"), int) and int(row["min_slack"]) < 0
            )
            warn_bits: list[str] = []
            if hold_n:
                warn_bits.append(
                    f"{hold_n} tras czeka na dopełnienie "
                    f"(poniżej {view.min_fill_ratio * 100:.0f}% i jest luz SLA)."
                )
            low = view.below_min_fill_count
            if low and not hold_n:
                warn_bits.append(
                    f"{low} tras poniżej progu zapełnienia (min. {view.min_fill_ratio * 100:.0f}%)."
                )
            if overdue_n:
                lead = settings.ship_lead_days
                warn_bits.append(
                    f"{overdue_n} tras spóźnionych względem wyjazdu {lead} dni przed terminem."
                )
            if warn_bits:
                fill_warn_label.set_text(" ".join(warn_bits))
                fill_warn_label.set_visibility(True)
            else:
                fill_warn_label.set_text("")
                fill_warn_label.set_visibility(False)
            riding_grid.options["rowData"] = view.riding
            riding_grid.update()
            staying_grid.options["rowData"] = view.staying
            staying_grid.update()
            staying_empty.set_visibility(len(view.staying) == 0)
            attention_grid.options["rowData"] = view.attention
            attention_grid.update()
            attention_empty.set_visibility(len(view.attention) == 0)
            tab_riding.set_label(f"Jedzie ({len(view.riding)})")
            tab_staying.set_label(f"Zostaje w magazynie ({len(view.staying)})")
            tab_attention.set_label(f"Wymaga uwagi ({len(view.attention)})")
            await sync_planning_state(ctx)

        async def on_enqueue_staying() -> None:
            if not staying_ids:
                ui.notify("Brak zleceń do dodania do kolejki.", type="info")
                return
            added = await run.io_bound(_enqueue_staying_job, staying_ids, username)
            ui.notify(
                f"Dodano do kolejki: {added}."
                if added
                else "Nic nie dodano (już w kolejce lub inny status).",
                type="positive" if added else "warning",
            )
            ui.navigate.to("/warehouse")

        async def on_generate() -> None:
            preferred = _active_run_id_from_storage()
            ctx_now = await run.io_bound(_load_planning_context, preferred)
            if (
                int(ctx_now["eligible_orders"]) == 0  # type: ignore[arg-type]
                or int(ctx_now["available_vehicles"]) == 0  # type: ignore[arg-type]
            ):
                await sync_planning_state(ctx_now)
                ui.notify(
                    "Brak zleceń w puli lub wolnych pojazdów — nie można generować.",
                    type="warning",
                )
                return
            warn_box.clear()
            result_label.set_visibility(False)
            generate_btn.disable()
            approve_btn.disable()
            gen_error.set_text("")
            gen_error.set_visibility(False)
            gen_close_btn.set_visibility(False)
            gen_progress.props("color=primary")
            gen_progress.set_value(0.1)
            gen_stage.set_text("Przygotowanie danych")
            gen_dialog.open()
            target = ctx_now.get("latest_run_id")
            target_id = int(target) if isinstance(target, int) else None
            try:
                request = await run.io_bound(_prepare_plan_job, target_id, False)
                gen_progress.set_value(0.15)
                gen_stage.set_text("Przydział pojazdów")
                gen_tick.activate()
                try:
                    assignment_stage = await run.cpu_bound(solve_assignment_stage, request)
                    gen_progress.set_value(0.35)
                    gen_stage.set_text("Macierz odległości")
                    bundle = await run.io_bound(
                        _build_routing_bundle_job, assignment_stage, request
                    )
                    gen_progress.set_value(0.5)
                    gen_stage.set_text("Optymalizacja tras")
                    routing = await run.cpu_bound(solve_routes_stage, request, bundle)
                    gen_progress.set_value(0.75)
                    gen_stage.set_text("Geometria tras")
                    prepared = await run.io_bound(
                        _finalize_plan_job,
                        request,
                        assignment_stage,
                        bundle,
                        routing,
                    )
                finally:
                    gen_tick.deactivate()
                if float(gen_progress.value or 0) < 0.9:
                    gen_progress.set_value(0.9)
                gen_progress.set_value(0.95)
                gen_stage.set_text("Zapis planu")
                (
                    run_id,
                    _status,
                    planned,
                    unassigned,
                    unrouted,
                    warnings,
                ) = await run.io_bound(_persist_plan_job, prepared, username)
                gen_progress.set_value(1.0)
                gen_stage.set_text("Gotowe")
                await asyncio.sleep(0.45)
                gen_dialog.close()
            except Exception as exc:
                gen_tick.deactivate()
                gen_progress.props("color=negative")
                gen_stage.set_text("Błąd")
                gen_error.set_text(str(exc))
                gen_error.set_visibility(True)
                gen_close_btn.set_visibility(True)
                await refresh_plan_view()
                ui.notify(str(exc), type="negative")
                return
            _set_active_run_id(run_id)
            await refresh_plan_view()
            result_label.set_text(
                f"Plan #{run_id} · jedzie={planned} · "
                f"zostaje={unassigned} · wymaga uwagi={unrouted}"
            )
            result_label.set_visibility(True)
            with warn_box:
                for msg in warnings[:30]:
                    ui.label(msg).classes("text-sm text-amber-800")
            ui.notify(
                f"Plan #{run_id}: jedzie {planned}, zostaje {unassigned}, wymaga uwagi {unrouted}.",
                type="positive" if unassigned == 0 and unrouted == 0 else "warning",
            )

        async def _selected_route_vehicle_ids() -> list[int]:
            rows = await routes_grid.get_selected_rows()
            ids: list[int] = []
            for row in rows:
                vid = row.get("vehicle_id")
                if vid is not None:
                    ids.append(int(vid))
            return ids

        async def on_approve_route() -> None:
            run_id = ctx.get("latest_run_id")
            if run_id is None:
                ui.notify("Brak planu.", type="warning")
                return
            vehicle_ids = await _selected_route_vehicle_ids()
            if not vehicle_ids:
                ui.notify("Zaznacz co najmniej jedną trasę w tabeli.", type="warning")
                return
            results: list[tuple[int, int, str]] = []
            errors: list[str] = []
            for vehicle_id in vehicle_ids:
                try:
                    results.append(
                        await run.io_bound(_approve_route_job, int(run_id), vehicle_id, username)
                    )
                except Exception as exc:
                    errors.append(f"pojazd {vehicle_id}: {exc}")
            if not results:
                ui.notify(
                    "Nie udało się zatwierdzić żadnej trasy: " + "; ".join(errors), type="negative"
                )
                return
            if len(results) == 1:
                rid, n_orders, code = results[0]
                ui.notify(
                    f"Zatwierdzono trasę {code} (plan #{rid}, {n_orders} zleceń).",
                    type="positive",
                )
            else:
                display = ", ".join(code for _, _, code in results[:5])
                if len(results) > 5:
                    display += "..."
                ui.notify(
                    f"Zatwierdzono {len(results)} tras: {display}.",
                    type="positive",
                )
            if errors:
                ui.notify(
                    "Część tras nie została zatwierdzona: " + "; ".join(errors[:3]), type="warning"
                )
            await refresh_plan_view()

        async def on_unlock_route() -> None:
            run_id = ctx.get("latest_run_id")
            if run_id is None:
                ui.notify("Brak planu.", type="warning")
                return
            vehicle_ids = await _selected_route_vehicle_ids()
            if not vehicle_ids:
                ui.notify("Zaznacz co najmniej jedną trasę w tabeli.", type="warning")
                return
            results: list[tuple[int, int, str]] = []
            errors: list[str] = []
            for vehicle_id in vehicle_ids:
                try:
                    results.append(
                        await run.io_bound(_unlock_route_job, int(run_id), vehicle_id, username)
                    )
                except Exception as exc:
                    errors.append(f"pojazd {vehicle_id}: {exc}")
            if not results:
                ui.notify(
                    "Nie udało się odblokować żadnej trasy: " + "; ".join(errors), type="negative"
                )
                return
            if len(results) == 1:
                rid, n_orders, code = results[0]
                ui.notify(
                    f"Odblokowano trasę {code} (plan #{rid}, {n_orders} zleceń wróciło do puli).",
                    type="info",
                )
            else:
                display = ", ".join(code for _, _, code in results[:5])
                if len(results) > 5:
                    display += "..."
                ui.notify(
                    f"Odblokowano {len(results)} tras: {display}.",
                    type="info",
                )
            if errors:
                ui.notify(
                    "Część tras nie mogła zostać odblokowana: " + "; ".join(errors[:3]),
                    type="warning",
                )
            await refresh_plan_view()

        async def on_complete_route() -> None:
            run_id = ctx.get("latest_run_id")
            if run_id is None:
                ui.notify("Brak planu.", type="warning")
                return
            vehicle_ids = await _selected_route_vehicle_ids()
            if not vehicle_ids:
                ui.notify("Zaznacz co najmniej jedną zatwierdzoną trasę w tabeli.", type="warning")
                return
            results: list[tuple[int, int, str]] = []
            errors: list[str] = []
            for vehicle_id in vehicle_ids:
                try:
                    results.append(
                        await run.io_bound(_complete_route_job, int(run_id), vehicle_id, username)
                    )
                except Exception as exc:
                    errors.append(f"pojazd {vehicle_id}: {exc}")
            if not results:
                ui.notify(
                    "Nie udało się oznaczyć żadnej trasy: " + "; ".join(errors), type="negative"
                )
                return
            if len(results) == 1:
                rid, n_orders, code = results[0]
                ui.notify(
                    f"Zrealizowano trasę {code} (plan #{rid}, {n_orders} zleceń). Auto wolne.",
                    type="positive",
                )
            else:
                display = ", ".join(code for _, _, code in results[:5])
                if len(results) > 5:
                    display += "..."
                ui.notify(
                    f"Zrealizowano {len(results)} tras: {display}.",
                    type="positive",
                )
            if errors:
                ui.notify(
                    "Część tras nie została oznaczona jako zrealizowana: " + "; ".join(errors[:3]),
                    type="warning",
                )
            await refresh_plan_view()

        async def on_approve() -> None:
            ctx_now = await run.io_bound(_load_planning_context, _active_run_id_from_storage())
            run_id = ctx_now.get("latest_run_id")
            if run_id is None or ctx_now.get("plan_status") not in {"draft", "partial"}:
                ui.notify("Brak propozycji tras do zatwierdzenia.", type="warning")
                return
            try:
                approved_run, count = await run.io_bound(
                    _approve_plan_job,
                    int(run_id),
                    username,  # type: ignore[arg-type]
                )
            except Exception as exc:
                await refresh_plan_view()
                ui.notify(str(exc), type="negative")
                return
            await refresh_plan_view()
            ui.notify(
                f"Zatwierdzono pełne trasy w planie #{approved_run}: {count} zleceń.",
                type="positive",
            )

        async def on_unlock() -> None:
            ctx_now = await run.io_bound(_load_planning_context, _active_run_id_from_storage())
            run_id = ctx_now.get("latest_run_id")
            if run_id is None or ctx_now.get("plan_status") not in {"approved", "partial"}:
                ui.notify("Odblokować można plan częściowy lub zatwierdzony.", type="warning")
                return
            try:
                unlocked_run, count = await run.io_bound(
                    _unlock_plan_job,
                    int(run_id),
                    username,  # type: ignore[arg-type]
                )
            except Exception as exc:
                await refresh_plan_view()
                ui.notify(str(exc), type="negative")
                return
            await refresh_plan_view()
            ui.notify(
                f"Odblokowano plan #{unlocked_run}: {count} zleceń → nowe.",
                type="positive",
            )

        async def on_delete_plan() -> None:
            ctx_now = await run.io_bound(_load_planning_context, _active_run_id_from_storage())
            run_id = ctx_now.get("latest_run_id")
            if run_id is None:
                ui.notify("Brak planu do usunięcia.", type="warning")
                return
            with ui.dialog() as dialog, ui.card().classes("p-4 gap-3"):
                ui.label(
                    f"Usunąć plan #{run_id}? Zlecenia z trasy wrócą do statusu „nowe”."
                ).classes("font-medium")
                with ui.row().classes("gap-2 justify-end w-full"):
                    ui.button("Anuluj", on_click=dialog.close).props("flat")

                    async def confirm() -> None:
                        dialog.close()
                        try:
                            deleted_run, count, remaining = await run.io_bound(
                                _delete_plan_job,
                                int(run_id),  # type: ignore[arg-type]
                                username,
                            )
                        except Exception as exc:
                            await refresh_plan_view()
                            ui.notify(str(exc), type="negative")
                            return
                        _set_active_run_id(remaining)
                        await refresh_plan_view()
                        ui.notify(
                            f"Usunięto plan #{deleted_run}: {count} zleceń → nowe.",
                            type="positive",
                        )

                    ui.button("Usuń plan", on_click=confirm).props("color=negative")
            dialog.open()

        async def on_show_map() -> None:
            ctx_now = await run.io_bound(_load_planning_context, _active_run_id_from_storage())
            run_id = ctx_now.get("latest_run_id")
            if run_id is None:
                ui.notify("Brak planu do wyświetlenia na mapie.", type="warning")
                return
            ui.navigate.to(f"/map?run_id={int(run_id)}")  # type: ignore[arg-type]

        async def on_plan_select(_e: object = None) -> None:
            if updating_plan_select:
                return
            raw = plan_select.value
            if raw is None:
                return
            chosen = int(raw)
            if chosen == ctx.get("latest_run_id"):
                return
            _set_active_run_id(chosen)
            await refresh_plan_view()

        async def on_rename_plan() -> None:
            run_id = ctx.get("latest_run_id")
            if run_id is None:
                ui.notify("Brak planu do nazwania.", type="warning")
                return
            current = str(ctx.get("display_name") or "")
            with ui.dialog() as dialog, ui.card().classes("p-4 gap-3 min-w-[320px]"):
                ui.label("Nazwa planu").classes("font-medium")
                name_in = ui.input(value=current).props(f"maxlength={PLAN_NAME_MAX_LEN}")
                name_in.classes("w-full")

                async def save_name() -> None:
                    try:
                        stored = await run.io_bound(
                            _rename_plan_job,
                            int(run_id),
                            str(name_in.value or ""),
                            username,
                        )
                    except Exception as exc:
                        ui.notify(str(exc), type="negative")
                        return
                    dialog.close()
                    ui.notify(
                        f"Zapisano nazwę: {stored}" if stored else "Usunięto nazwę planu.",
                        type="positive",
                    )
                    await refresh_plan_view()

                with ui.row().classes("gap-2 justify-end w-full"):
                    ui.button("Anuluj", on_click=dialog.close).props("flat")
                    ui.button("Zapisz", on_click=save_name).props("color=primary")
            dialog.open()

        async def on_new_plan() -> None:
            try:
                new_id = await run.io_bound(_create_empty_plan_job, username)
            except Exception as exc:
                ui.notify(str(exc), type="negative")
                return
            _set_active_run_id(new_id)
            await refresh_plan_view()
            ui.notify(f"Utworzono nowy plan #{new_id}.", type="positive")

        plan_select.on_value_change(on_plan_select)
        rename_btn.on_click(on_rename_plan)
        new_plan_btn.on_click(on_new_plan)
        refresh_btn.on_click(refresh_plan_view)
        generate_btn.on_click(on_generate)
        approve_btn.on_click(on_approve)
        approve_route_btn.on_click(on_approve_route)
        complete_route_btn.on_click(on_complete_route)
        unlock_route_btn.on_click(on_unlock_route)
        unlock_btn.on_click(on_unlock)
        delete_plan_btn.on_click(on_delete_plan)
        map_btn.on_click(on_show_map)
        enqueue_staying_btn.on_click(on_enqueue_staying)
        await refresh_plan_view()


def _load_map_view(run_id: int | None, require_exact: bool = False) -> MapPlanView | None:
    with session_scope() as session:
        service = MapViewService(session)
        if require_exact:
            if run_id is None:
                return None
            return service.build_for_run(run_id)
        resolved = PlanningService(session).resolve_run_id(run_id)
        if resolved is None:
            return None
        return service.build_for_run(resolved)


@ui.page("/map")
async def map_page(run_id: int | None = None) -> None:
    with page_frame("Mapa"):
        ops_page_header(
            "Mapa",
            "Trasy aktywnego planu. Linie łączą magazyn z punktami rozładunku "
            "(po drogach, gdy włączono OSRM); strzałki pokazują kierunek jazdy.",
        )
        chosen_explicit = run_id is not None
        chosen = run_id if chosen_explicit else _active_run_id_from_storage()
        view = await run.io_bound(_load_map_view, chosen, chosen_explicit)
        if view is None:
            with ui.element("div").classes("cd-ops-panel w-full"):
                ui.label("Brak planu do wyświetlenia.").classes("font-bold text-lg")
                ui.label("Wygeneruj plan na stronie Plany, potem wróć tutaj.").classes(
                    "text-gray-600"
                )
                ui.button("Przejdź do Planów", on_click=lambda: ui.navigate.to("/plans"))
            return

        with ui.element("div").classes("cd-ops-panel w-full"):
            ui.label(
                format_plan_label(
                    run_id=view.run_id,
                    display_name=view.display_name,
                    plan_status=view.plan_status,
                    created_at=view.created_at,
                )
                + f" · pojazdów na mapie: {len(view.routes)}"
            ).classes("font-medium")

        with ui.row().classes("w-full gap-4 items-start flex-wrap"):
            with (
                ui.element("div")
                .classes("cd-ops-panel")
                .style("min-width:200px;flex:0 0 auto;padding:0.75rem 1rem;")
            ):
                ui.label("Legenda").classes("font-medium").style("color: var(--cd-heading)")
                for route in view.routes:
                    km = f"{route.distance_km:.1f} km" if route.distance_km is not None else "?"
                    status_pl = route_status_pl(route.route_status)
                    with ui.row().classes("items-center gap-2"):
                        ui.element("div").style(
                            f"width:14px;height:14px;border-radius:2px;background:{route.color};"
                            + ("opacity:0.45;" if route.route_status != "approved" else "")
                        )
                        ui.label(
                            f"{route.vehicle_code} · {status_pl} · {len(route.markers)} pkt · {km}"
                        ).classes("text-sm").style("color: var(--cd-body)")

            m = (
                ui.leaflet(center=view.center, zoom=view.zoom)
                .classes("flex-grow")
                .style("height: 70vh; min-width: 320px;")
            )
            depot_marker = m.marker(
                latlng=(view.depot.latitude, view.depot.longitude),
                options={"title": "Magazyn"},
            )
            route_markers: list[tuple[object, str]] = []
            arrows: list[dict[str, float | str]] = []
            for route in view.routes:
                approved = route.route_status == "approved"
                m.generic_layer(
                    name="polyline",
                    args=[
                        list(route.polyline),
                        {
                            "color": route.color,
                            "weight": 5 if approved else 3,
                            "opacity": 0.9 if approved else 0.45,
                            "dashArray": None if approved else "8 8",
                        },
                    ],
                )
                arrows.extend(segment_arrows(route.polyline, color=route.color))
                for point in route.markers:
                    mk = m.marker(
                        latlng=(point.latitude, point.longitude),
                        options={"title": point.label},
                    )
                    route_markers.append((mk, point.popup_html))

            await m.initialized()
            depot_marker.run_method("bindPopup", view.depot.popup_html)
            for mk, html in route_markers:
                mk.run_method("bindPopup", html)  # type: ignore[attr-defined]

            if arrows:
                payload = json.dumps(arrows, ensure_ascii=False)
                ui.run_javascript(
                    f"""
                    (() => {{
                      const host = document.getElementById('c' + {m.id});
                      const map = host && (host.map || (host.__vueParentComponent
                        && host.__vueParentComponent.ctx
                        && host.__vueParentComponent.ctx.map));
                      if (!map || !window.L) return;
                      const arrows = {payload};
                      arrows.forEach(a => {{
                        const icon = L.divIcon({{
                          className: '',
                          html: '<div style="transform:rotate(' + a.bearing +
                            'deg);color:' + a.color +
                            ';font-size:18px;text-shadow:0 0 3px #fff;">▲</div>',
                          iconSize: [20, 20],
                          iconAnchor: [10, 10],
                        }});
                        L.marker([a.lat, a.lon], {{icon: icon}}).addTo(map);
                      }});
                    }})();
                    """
                )

            lats = [view.depot.latitude]
            lons = [view.depot.longitude]
            for route in view.routes:
                for lat, lon in route.polyline:
                    lats.append(lat)
                    lons.append(lon)
            if len(lats) > 1:
                m.run_map_method(
                    "fitBounds",
                    [[min(lats), min(lons)], [max(lats), max(lons)]],
                    {"padding": [40, 40]},
                )


@ui.page("/reports")
async def reports_page() -> None:
    with page_frame("Raporty"):
        ops_page_header(
            "Raporty",
            "Zapełnienie wagowe pojazdów oraz oszczędności względem "
            "scenariusza 1 zlecenie = 1 pojazd. Stawka za km z ustawień.",
        )
        with ui.element("div").classes("cd-ops-hero w-full"):
            ui.label("Efektywność planu").classes("font-bold")

        summary = ui.label("").classes("text-sm")
        reports_host = ui.element("div").classes("cd-grid-host")
        with reports_host:
            util_grid = (
                ui.aggrid(
                    {
                        "columnDefs": [
                            {"headerName": "Pojazd", "field": "vehicle"},
                            {"headerName": "Status", "field": "route_status_pl"},
                            {"headerName": "Punkty rozładunku", "field": "drops"},
                            {"headerName": "Zapełnienie %", "field": "fill"},
                            {"headerName": "Km", "field": "km"},
                            {"headerName": "Koszt €", "field": "cost"},
                        ],
                        "rowData": [],
                        "domLayout": "normal",
                    }
                )
                .classes("w-full")
                .style("height: 280px")
            )

        async def refresh_report() -> None:
            bundle = await run.io_bound(_load_report, _active_run_id_from_storage())
            if bundle is None:
                summary.set_text("Brak planu do raportu.")
                util_grid.options["rowData"] = []
                util_grid.update()
                return
            sav = bundle.savings
            label = format_plan_label(
                run_id=bundle.run_id,
                display_name=bundle.display_name,
                plan_status=bundle.plan_status,
                created_at=bundle.created_at,
            )
            summary.set_text(
                f"{label} · oszczędność {sav.savings_eur:.0f} € ({sav.savings_pct:.0f}%)"
            )
            util_grid.options["rowData"] = [
                {
                    "vehicle": r.vehicle_code,
                    "route_status_pl": route_status_pl(r.route_status),
                    "drops": r.drop_count,
                    "fill": (round(r.fill_ratio * 100, 1) if r.fill_ratio is not None else "?"),
                    "km": round(r.distance_km, 1),
                    "cost": round(r.cost_eur, 2),
                }
                for r in bundle.utilization
            ]
            util_grid.update()

        async def on_download() -> None:
            data = await run.io_bound(_export_report_bytes, _active_run_id_from_storage())
            if data is None:
                ui.notify("Brak raportu do pobrania.", type="warning")
                return
            ui.download(data, "raport_crossdock.xlsx")

        with ui.row().classes("cd-toolbar"):
            ui.button("Odśwież", on_click=refresh_report).props("outline")
            ui.button("Pobierz Excel", icon="download", on_click=on_download).props("color=primary")
            enlarge_grid_button(
                util_grid,
                reports_host,
                title="Raport",
                compact_height="280px",
            )
        await refresh_report()


def _load_report(run_id: int | None = None) -> ReportBundle | None:
    with session_scope() as session:
        resolved = PlanningService(session).resolve_run_id(run_id)
        if resolved is None:
            return None
        return build_report(session, run_id=resolved)


def _export_report_bytes(run_id: int | None = None) -> bytes | None:
    with session_scope() as session:
        resolved = PlanningService(session).resolve_run_id(run_id)
        if resolved is None:
            return None
        bundle = build_report(session, run_id=resolved)
        if bundle is None:
            return None
        return export_report_xlsx(bundle)


@ui.page("/warehouse")
async def warehouse_page() -> None:
    username = app.storage.user.get("username", "unknown")
    with page_frame("Magazyn"):
        ops_page_header(
            "Magazyn",
            "Stan zapełnienia, odliczanie do wyjazdu i bufor. "
            "Zlecenia trafiają od razu do dalszej obsługi według planu i priorytetów biznesowych.",
        )

        with ui.element("div").classes("cd-wh-card w-full"):
            ui.label("Stan magazynu").classes("cd-wh-card-title")
            with ui.row().classes("w-full items-baseline gap-4 flex-wrap"):
                occ_used = ui.label("— kg").classes("text-xl font-bold")
                occ_cap = ui.label("—").classes("text-sm text-gray-600")
                occ_slack = ui.label("—").classes("text-sm")
            occ_warn = ui.label("").classes("text-sm text-red-700")
            occ_warn.set_visibility(False)

        with ui.element("div").classes("cd-wh-card w-full"):
            with ui.row().classes("w-full items-center justify-between"):
                with ui.row().classes("items-center gap-1"):
                    ui.label("Do kolejki").classes("cd-wh-card-title")
                    info_hint("Zlecenia ze statusem „nowe”, które jeszcze nie są w kolejce wydań.")
                enlarge_candidates_btn = ui.button("Powiększ", icon="open_in_full").props(
                    "flat dense no-caps"
                )
            candidates_host = ui.element("div").classes("cd-grid-host")
            with candidates_host:
                candidates_grid = (
                    ui.aggrid(
                        {
                            "columnDefs": [
                                selection_column(multiple=True),
                                {"headerName": "ID", "field": "order_id", "width": 80},
                                {"headerName": "Kod", "field": "delivery_code", "filter": True},
                                {"headerName": "Miasto", "field": "city", "filter": True},
                                {"headerName": "Waga [kg]", "field": "weight_kg", "sortable": True},
                                {"headerName": "Termin", "field": "delivery_date"},
                                {"headerName": "Wyjechać do", "field": "must_leave_on"},
                                {
                                    "headerName": "Luz [dni]",
                                    "field": "slack_days",
                                    "sortable": True,
                                },
                            ],
                            "rowData": [],
                            "rowSelection": "multiple",
                            "suppressRowClickSelection": True,
                            "domLayout": "normal",
                        }
                    )
                    .classes("w-full")
                    .style("height: 200px")
                )
            with ui.row().classes("cd-toolbar"):
                enqueue_btn = ui.button("Dodaj do kolejki", icon="playlist_add").props(
                    "color=primary"
                )
                candidates_empty = ui.label("Brak dostępnych zleceń „nowe” poza kolejką.").classes(
                    "text-sm text-gray-500"
                )

        with ui.element("div").classes("cd-wh-card w-full"):
            with ui.row().classes("w-full items-center justify-between"):
                with ui.row().classes("items-center gap-1"):
                    ui.label("Kolejka wydań").classes("cd-wh-card-title")
                    info_hint("Priorytet góra/dół i wstrzymanie — całe zlecenia (FR-019).")
                enlarge_queue_btn = ui.button("Powiększ", icon="open_in_full").props(
                    "flat dense no-caps"
                )
            queue_host = ui.element("div").classes("cd-grid-host")
            with queue_host:
                grid = (
                    ui.aggrid(
                        {
                            "columnDefs": [
                                selection_column(multiple=False),
                                {"headerName": "Poz.", "field": "position", "width": 70},
                                {"headerName": "Kod", "field": "delivery_code", "filter": True},
                                {"headerName": "Miasto", "field": "city"},
                                {"headerName": "Waga [kg]", "field": "weight_kg"},
                                {"headerName": "Termin", "field": "delivery_date"},
                                {"headerName": "Wyjechać do", "field": "must_leave_on"},
                                {
                                    "headerName": "Luz [dni]",
                                    "field": "slack_days",
                                    "sortable": True,
                                },
                                {"headerName": "Status", "field": "status"},
                                {"headerName": "ID", "field": "order_id", "width": 80},
                            ],
                            "rowData": [],
                            "rowSelection": "single",
                            "suppressRowClickSelection": True,
                            "domLayout": "normal",
                        }
                    )
                    .classes("w-full")
                    .style("height: 240px")
                )
            queue_empty = ui.label(
                "Brak pozycji — dodaj zlecenie z listy powyżej lub z Planów."
            ).classes("text-sm text-gray-500")
            with ui.row().classes("cd-toolbar"):
                ui.button(
                    "W górę",
                    icon="arrow_upward",
                    on_click=lambda: _move("up"),
                ).props("outline")
                ui.button(
                    "W dół",
                    icon="arrow_downward",
                    on_click=lambda: _move("down"),
                ).props("outline")
                ui.button("Wstrzymaj", on_click=lambda: _hold(True)).props("outline")
                ui.button("Wznów", on_click=lambda: _hold(False)).props("outline")
                ui.button(
                    "Usuń z kolejki",
                    on_click=lambda: _remove(),
                ).props("outline color=negative")
                ui.button("Odśwież", on_click=lambda: refresh_all()).props("flat")

        with ui.element("div").classes("cd-wh-card w-full"):
            with ui.row().classes("w-full items-center justify-between"):
                with ui.row().classes("items-center gap-1"):
                    ui.label("W drodze").classes("cd-wh-card-title")
                    info_hint(
                        "Zatwierdzone trasy aktywnego planu, które jeszcze nie wróciły. "
                        "Zrealizowane = auto wolne, zlecenia dostarczone, trasa zostaje w historii."
                    )
                enlarge_transit_btn = ui.button("Powiększ", icon="open_in_full").props(
                    "flat dense no-caps"
                )
            transit_host = ui.element("div").classes("cd-grid-host")
            with transit_host:
                transit_grid = (
                    ui.aggrid(
                        {
                            "columnDefs": [
                                selection_column(multiple=True),
                                {"headerName": "Pojazd", "field": "vehicle", "filter": True},
                                {
                                    "headerName": "Zlecenia",
                                    "field": "order_count",
                                    "width": 110,
                                },
                                {"headerName": "Km", "field": "distance_km", "width": 90},
                                {"headerName": "Status", "field": "route_status_pl"},
                            ],
                            "rowData": [],
                            "rowSelection": "multiple",
                            "suppressRowClickSelection": True,
                            "domLayout": "normal",
                        }
                    )
                    .classes("w-full")
                    .style("height: 180px")
                )
            transit_empty = ui.label("Brak zatwierdzonych tras w drodze.").classes(
                "text-sm text-gray-500"
            )
            with ui.row().classes("cd-toolbar"):
                complete_wh_btn = ui.button("Zrealizowane", icon="done").props("color=positive")

        with ui.element("div").classes("cd-wh-card w-full"):
            with ui.row().classes("w-full items-center justify-between"):
                with ui.row().classes("items-center gap-1"):
                    ui.label("Propozycja buforowania").classes("cd-wh-card-title")
                    info_hint("Oszczędność kosztowa: przytrzymaj towar albo wyślij teraz.")
                enlarge_buffer_btn = ui.button("Powiększ", icon="open_in_full").props(
                    "flat dense no-caps"
                )
            buffer_summary = ui.label(
                "Kliknij „Odśwież propozycję”, aby policzyć buforowanie kosztowe."
            ).classes("text-sm text-gray-700")
            buffer_decisions: dict[int, object] = {}
            buffer_host = ui.element("div").classes("cd-grid-host")
            with buffer_host:
                buffer_grid = (
                    ui.aggrid(
                        {
                            "columnDefs": [
                                selection_column(multiple=True),
                                {"headerName": "Kod", "field": "delivery_code"},
                                {"headerName": "ID", "field": "order_id", "width": 80},
                                {"headerName": "Decyzja", "field": "action"},
                                {"headerName": "Dni", "field": "buffer_days"},
                                {"headerName": "Oszczędność %", "field": "savings_pct"},
                            ],
                            "rowData": [],
                            "rowSelection": "multiple",
                            "suppressRowClickSelection": True,
                            "domLayout": "normal",
                        }
                    )
                    .classes("w-full")
                    .style("height: 220px")
                )
            with ui.row().classes("cd-toolbar"):
                refresh_buffer_btn = ui.button("Odśwież propozycję", icon="calculate").props(
                    "outline"
                )
                accept_buffer_btn = ui.button("Akceptuj zaznaczone", icon="check").props(
                    "color=primary"
                )

        async def refresh_all() -> None:
            try:
                candidates, entries, in_transit, snap = await run.io_bound(
                    _load_warehouse_view, _active_run_id_from_storage()
                )
            except Exception as exc:
                ui.notify(f"Nie udało się wczytać kolejki: {exc}", type="negative")
                return
            candidates_grid.options["rowData"] = [
                {
                    "order_id": e.order_id,
                    "delivery_code": e.delivery_code,
                    "city": e.city,
                    "weight_kg": (round(e.weight_kg, 1) if e.weight_kg is not None else "?"),
                    "delivery_date": (
                        e.delivery_date.isoformat() if e.delivery_date is not None else "—"
                    ),
                    "must_leave_on": (
                        e.must_leave_on.isoformat() if e.must_leave_on is not None else "—"
                    ),
                    "slack_days": e.slack_days if e.slack_days is not None else "—",
                }
                for e in candidates
            ]
            candidates_grid.update()
            candidates_empty.set_visibility(len(candidates) == 0)
            grid.options["rowData"] = [
                {
                    "position": e.position,
                    "delivery_code": e.delivery_code,
                    "city": e.city,
                    "weight_kg": (round(e.weight_kg, 1) if e.weight_kg is not None else "?"),
                    "delivery_date": (
                        e.delivery_date.isoformat() if e.delivery_date is not None else "—"
                    ),
                    "must_leave_on": (
                        e.must_leave_on.isoformat() if e.must_leave_on is not None else "—"
                    ),
                    "slack_days": e.slack_days if e.slack_days is not None else "—",
                    "status": queue_status_pl(e.status),
                    "order_id": e.order_id,
                }
                for e in entries
            ]
            grid.update()
            queue_empty.set_visibility(len(entries) == 0)
            transit_grid.options["rowData"] = [
                {
                    "vehicle_id": r.vehicle_id,
                    "vehicle": r.vehicle_code,
                    "order_count": r.order_count,
                    "distance_km": r.distance_km,
                    "route_status_pl": route_status_pl(r.route_status),
                }
                for r in in_transit
            ]
            transit_grid.update()
            transit_empty.set_visibility(len(in_transit) == 0)
            occ_used.set_text(
                f"{snap.used_kg:.0f} kg ({snap.fill_ratio * 100:.0f}%) · {snap.order_count} zleceń"
            )
            occ_cap.set_text(
                f"pojemność {snap.capacity_kg:.0f} kg · dzień {snap.planning_date.isoformat()}"
            )
            if snap.nearest_must_leave is not None:
                slack_txt = (
                    f"luz {snap.nearest_slack} dni" if snap.nearest_slack is not None else ""
                )
                occ_slack.set_text(
                    f"najbliższy wyjazd {snap.nearest_must_leave.isoformat()} ({slack_txt})"
                )
            else:
                occ_slack.set_text("brak towaru w magazynie")
            if snap.overflow:
                occ_warn.set_text(
                    "Magazyn ponad pojemność — solver wypchnie najpilniejsze zlecenia."
                )
                occ_warn.set_visibility(True)
            else:
                occ_warn.set_text("")
                occ_warn.set_visibility(False)

        async def on_enqueue_selected() -> None:
            selected = await candidates_grid.get_selected_rows()
            if not selected:
                ui.notify("Zaznacz zlecenie z listy dostępnych.", type="warning")
                return
            added = 0
            for row in selected:
                try:
                    await run.io_bound(_enqueue_job, int(row["order_id"]), username)
                    added += 1
                except Exception as exc:
                    ui.notify(str(exc), type="negative")
            if added:
                ui.notify(f"Dodano do kolejki: {added}.", type="positive")
            await refresh_all()

        async def _selected_order_id() -> int | None:
            rows = await grid.get_selected_rows()
            if not rows:
                ui.notify("Zaznacz pozycję w kolejce.", type="warning")
                return None
            return int(rows[0]["order_id"])

        async def _move(direction: str) -> None:
            oid = await _selected_order_id()
            if oid is None:
                return
            await run.io_bound(_move_job, oid, direction, username)
            await refresh_all()

        async def _hold(held: bool) -> None:
            oid = await _selected_order_id()
            if oid is None:
                return
            await run.io_bound(_hold_job, oid, held, username)
            await refresh_all()

        async def _remove() -> None:
            oid = await _selected_order_id()
            if oid is None:
                return
            await run.io_bound(_dequeue_job, oid, username)
            ui.notify("Usunięto z kolejki.", type="positive")
            await refresh_all()

        async def on_complete_in_transit() -> None:
            rows = await transit_grid.get_selected_rows()
            if not rows:
                ui.notify("Zaznacz co najmniej jedną trasę w drodze.", type="warning")
                return
            run_id = _active_run_id_from_storage()
            if run_id is None:
                ui.notify("Brak aktywnego planu.", type="warning")
                return
            results: list[tuple[int, int, str]] = []
            errors: list[str] = []
            for row in rows:
                vehicle_id = row.get("vehicle_id")
                if vehicle_id is None:
                    errors.append(f"{row.get('vehicle', '?')}: brak pojazdu")
                    continue
                try:
                    results.append(
                        await run.io_bound(
                            _complete_route_job, int(run_id), int(vehicle_id), username
                        )
                    )
                except Exception as exc:
                    errors.append(f"{row.get('vehicle', vehicle_id)}: {exc}")
            if not results:
                ui.notify(
                    "Nie udało się oznaczyć żadnej trasy: " + "; ".join(errors),
                    type="negative",
                )
                return
            if len(results) == 1:
                rid, n_orders, code = results[0]
                ui.notify(
                    f"Zrealizowano trasę {code} (plan #{rid}, {n_orders} zleceń). Auto wolne.",
                    type="positive",
                )
            else:
                display = ", ".join(code for _, _, code in results[:5])
                if len(results) > 5:
                    display += "..."
                ui.notify(
                    f"Zrealizowano {len(results)} tras: {display}.",
                    type="positive",
                )
            if errors:
                ui.notify(
                    "Część tras nie została oznaczona jako zrealizowana: " + "; ".join(errors[:3]),
                    type="warning",
                )
            await refresh_all()

        async def refresh_buffer() -> None:
            nonlocal buffer_decisions
            try:
                bundle = await run.io_bound(_propose_buffer_job)
            except Exception as exc:
                ui.notify(f"Błąd propozycji: {exc}", type="negative")
                return
            buffer_decisions = {d.order_id: d for d in bundle.decisions}
            buffer_grid.options["rowData"] = [
                {
                    "delivery_code": d.delivery_code,
                    "order_id": d.order_id,
                    "action": buffer_action_pl(d.action),
                    "buffer_days": d.buffer_days,
                    "savings_pct": round(d.savings_ratio * 100, 1),
                    "_code": d.action,
                }
                for d in bundle.decisions
            ]
            buffer_grid.update()
            buffer_summary.set_text(
                f"Kandydaci: {len(bundle.decisions)} · "
                f"przytrzymaj: {bundle.buffer_count} · "
                f"wyślij teraz: {bundle.ship_now_count}"
            )

        async def on_accept_buffer() -> None:
            selected = await buffer_grid.get_selected_rows()
            if not selected:
                ui.notify("Zaznacz propozycje „przytrzymaj”.", type="warning")
                return
            ids = [int(r["order_id"]) for r in selected if r.get("_code") == "buffer"]
            if not ids:
                ui.notify("Zaznacz wiersze z decyzją „przytrzymaj”.", type="warning")
                return
            accepted = await run.io_bound(_accept_buffer_job, ids, buffer_decisions, username)
            ui.notify(f"Zaakceptowano: {accepted}.", type="positive" if accepted else "warning")
            await refresh_all()
            await refresh_buffer()

        def _queue_enlarge_toolbar() -> None:
            ui.button("W górę", icon="arrow_upward", on_click=lambda: _move("up")).props("outline")
            ui.button("W dół", icon="arrow_downward", on_click=lambda: _move("down")).props(
                "outline"
            )
            ui.button("Wstrzymaj", on_click=lambda: _hold(True)).props("outline")
            ui.button("Wznów", on_click=lambda: _hold(False)).props("outline")
            ui.button("Usuń z kolejki", on_click=lambda: _remove()).props("outline color=negative")
            ui.button("Odśwież", on_click=lambda: refresh_all()).props("flat")

        def _buffer_enlarge_toolbar() -> None:
            ui.button(
                "Odśwież propozycję",
                icon="calculate",
                on_click=refresh_buffer,
            ).props("outline")
            ui.button(
                "Akceptuj zaznaczone",
                icon="check",
                on_click=on_accept_buffer,
            ).props("color=primary")

        enqueue_btn.on_click(on_enqueue_selected)
        complete_wh_btn.on_click(on_complete_in_transit)
        refresh_buffer_btn.on_click(refresh_buffer)
        accept_buffer_btn.on_click(on_accept_buffer)

        enlarge_candidates_btn.on_click(
            attach_grid_enlarge(
                candidates_grid,
                candidates_host,
                title="Do kolejki",
                compact_height="200px",
                toolbar_builder=lambda: ui.button(
                    "Dodaj do kolejki",
                    icon="playlist_add",
                    on_click=on_enqueue_selected,
                ).props("color=primary"),
            )
        )
        enlarge_queue_btn.on_click(
            attach_grid_enlarge(
                grid,
                queue_host,
                title="Kolejka wydań",
                compact_height="240px",
                toolbar_builder=_queue_enlarge_toolbar,
            )
        )
        enlarge_transit_btn.on_click(
            attach_grid_enlarge(
                transit_grid,
                transit_host,
                title="W drodze",
                compact_height="180px",
                toolbar_builder=lambda: ui.button(
                    "Zrealizowane",
                    icon="done",
                    on_click=on_complete_in_transit,
                ).props("color=positive"),
            )
        )
        enlarge_buffer_btn.on_click(
            attach_grid_enlarge(
                buffer_grid,
                buffer_host,
                title="Propozycja buforowania",
                compact_height="220px",
                toolbar_builder=_buffer_enlarge_toolbar,
            )
        )

        await refresh_all()


def _load_warehouse_view(run_id: int | None = None):
    with session_scope() as session:
        return (
            list_enqueue_candidates(session),
            list_queue(session),
            list_in_transit_routes(session, run_id=run_id),
            warehouse_snapshot(session, run_id=run_id),
        )


def _propose_buffer_job():
    with session_scope() as session:
        return compute_buffer_proposals(session)


def _accept_buffer_job(order_ids: list[int], decisions_by_id: dict, username: str) -> int:
    with session_scope() as session:
        return accept_buffer_proposals(
            session,
            order_ids=order_ids,
            decisions_by_id=decisions_by_id,
            username=username,
        )


def _enqueue_job(order_id: int, username: str):
    with session_scope() as session:
        return enqueue_order(session, order_id=order_id, username=username)


def _dequeue_job(order_id: int, username: str) -> bool:
    with session_scope() as session:
        return dequeue_order(session, order_id=order_id, username=username)


def _move_job(order_id: int, direction: str, username: str):
    with session_scope() as session:
        return move_order(session, order_id=order_id, direction=direction, username=username)


def _hold_job(order_id: int, held: bool, username: str):
    with session_scope() as session:
        return set_held(session, order_id=order_id, held=held, username=username)


def _fmt_bytes(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f} GB"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} MB"
    if n >= 1_000:
        return f"{n / 1_000:.1f} KB"
    return f"{n} B"


def _load_system_status():
    with session_scope() as session:
        return collect_system_status(session)


def _read_log_job(filename: str, max_bytes: int, max_lines: int):
    return read_log_file(filename, max_bytes=max_bytes, max_lines=max_lines)


def _run_backup_job():
    return run_backup()


@ui.page("/system")
async def system_page() -> None:
    with page_frame("Stan systemu"):
        ops_page_header(
            "Stan systemu",
            "Podgląd bazy, planu, dysku, kopii zapasowej i ogona logów.",
        )
        with ui.element("div").classes("cd-ops-hero w-full"):
            ui.label("Stan systemu").classes("font-bold")
        with ui.row().classes("cd-toolbar"):
            refresh_btn = ui.button("Odśwież", icon="refresh").props("outline")
            backup_btn = ui.button("Utwórz kopię teraz", icon="backup").props("color=primary")
            log_select = (
                ui.select(options={}, value=None, label="Plik logu")
                .classes("min-w-[16rem]")
                .props("dense options-dense")
            )
            show_log_btn = ui.button("Pokaż log", icon="article").props("outline")
        status_box = ui.column().classes("w-full gap-2")
        log_box = ui.column().classes("w-full gap-1 font-mono text-xs")

        async def refresh_status() -> None:
            status_box.clear()
            log_box.clear()
            try:
                st = await run.io_bound(_load_system_status)
            except Exception as exc:
                ui.notify(f"Nie udało się odczytać statusu: {exc}", type="negative")
                return
            with status_box:
                ui.label(f"Baza: {st.db_path}").classes("text-sm")
                wal = "tak" if st.wal_mode else "nie"
                ui.label(
                    f"Rozmiar: {_fmt_bytes(st.db_size_bytes)} · WAL: {wal} · "
                    f"zlecenia: {st.order_count}"
                ).classes("text-sm")
                ui.label(
                    f"Dysk wolny: {_fmt_bytes(st.disk_free_bytes)} / "
                    f"{_fmt_bytes(st.disk_total_bytes)}"
                ).classes("text-sm")
                if st.latest_plan_id is None:
                    ui.label("Ostatni plan: brak").classes("text-sm")
                else:
                    ui.label(
                        f"Ostatni plan #{st.latest_plan_id} · "
                        f"{plan_status_pl(st.latest_plan_status)}"
                    ).classes("text-sm")
                ui.label(f"Ostatni import: {st.last_import_summary or 'brak'}").classes("text-sm")
                if st.last_backup_path:
                    ui.label(
                        f"Ostatnia kopia: {st.last_backup_path} · {st.last_backup_mtime}"
                    ).classes("text-sm")
                else:
                    ui.label("Ostatnia kopia: brak").classes("text-sm")
            files = list(st.log_files)
            if files:
                log_select.set_options({name: name for name in files}, value=files[0])
                log_select.enable()
                show_log_btn.enable()
            else:
                log_select.set_options({"_none": "Brak plików logów"}, value="_none")
                log_select.disable()
                show_log_btn.disable()
            with log_box:
                ui.label("Ogon logu (najnowszy plik):").classes("text-sm font-medium font-sans")
                if st.log_tail:
                    for line in st.log_tail:
                        ui.label(line)
                else:
                    ui.label("Brak plików logów").classes("font-sans")

        async def _open_log_dialog(*, more: bool) -> None:
            filename = log_select.value
            if not filename or filename == "_none":
                ui.notify("Brak plików logów.", type="info")
                return
            max_bytes = LOG_FULL_BYTES if more else LOG_PREVIEW_BYTES
            max_lines = 80_000 if more else LOG_PREVIEW_LINES
            try:
                view = await run.io_bound(_read_log_job, str(filename), max_bytes, max_lines)
            except Exception as exc:
                ui.notify(f"Nie udało się odczytać logu: {exc}", type="negative")
                return
            with (
                ui.dialog() as dialog,
                ui.card()
                .classes("p-4 gap-2")
                .style("width:90vw;height:85vh;max-width:90vw;display:flex;flex-direction:column;"),
            ):
                ui.label(view.filename).classes("font-medium")
                if view.truncated:
                    ui.label("Pokazano ogon pliku — treść ucięta (limit odczytu).").classes(
                        "text-sm text-amber-800"
                    )
                body = "\n".join(view.lines) if view.lines else "(pusty plik)"
                with ui.scroll_area().classes("w-full").style("flex:1;min-height:0;"):
                    ui.code(body).classes("w-full font-mono text-xs")
                with ui.row().classes("gap-2 justify-end w-full"):
                    if view.truncated and not more:

                        async def load_more() -> None:
                            dialog.close()
                            await _open_log_dialog(more=True)

                        ui.button("Wczytaj więcej", on_click=load_more).props("outline")
                    ui.button("Zamknij", on_click=dialog.close).props("color=primary")
            dialog.open()

        async def on_show_log() -> None:
            await _open_log_dialog(more=False)

        async def on_backup_now() -> None:
            try:
                result = await run.io_bound(_run_backup_job)
            except Exception as exc:
                ui.notify(f"Kopia nieudana: {exc}", type="negative")
                return
            ui.notify(
                f"Utworzono kopię: {result.path.name} ({_fmt_bytes(result.size_bytes)}).",
                type="positive",
            )
            await refresh_status()

        refresh_btn.on_click(refresh_status)
        backup_btn.on_click(on_backup_now)
        show_log_btn.on_click(on_show_log)
        await refresh_status()


def _vehicles_to_rows(vehicles: list[Vehicle]) -> list[dict[str, object]]:
    return [
        {
            "id": v.id,
            "code": v.code,
            "vehicle_type": v.vehicle_type.value,
            "pallet_capacity": v.pallet_capacity,
            "weight_capacity_kg": v.weight_capacity_kg,
            "is_active": "tak" if v.is_active else "nie",
            "is_placeholder": "tak" if v.is_placeholder else "nie",
            "is_busy": "tak" if v.is_busy else "nie",
        }
        for v in vehicles
    ]


def _load_fleet_type_overview() -> list[dict[str, object]]:
    from crossdock.services.fleet import fleet_type_counts, fleet_type_specs

    with session_scope() as session:
        counts = fleet_type_counts(session)
    rows: list[dict[str, object]] = []
    for spec in fleet_type_specs():
        vtype = str(spec["vehicle_type"])
        c = counts.get(vtype, {"active": 0, "busy": 0, "total": 0})
        rows.append(
            {
                **spec,
                "active_count": c["active"],
                "busy_count": c["busy"],
                "target_count": c["active"],
            }
        )
    return rows


def _sync_fleet_type_job(
    vehicle_type: str, target_count: int, username: str
) -> tuple[int, int, int, int]:
    from crossdock.services.fleet import sync_fleet_units

    with session_scope() as session:
        result = sync_fleet_units(
            session,
            vehicle_type=VehicleType(vehicle_type),
            target_count=target_count,
            username=username,
        )
    return result.created, result.activated, result.deactivated, result.skipped_busy


def _load_vehicles() -> list[Vehicle]:
    with session_scope() as session:
        return VehicleRepository(session).list_all()


def _save_vehicle(
    *,
    vehicle_id: int | None,
    code: str,
    vehicle_type: str,
    pallet_capacity: int,
    weight_capacity_kg: float,
    is_active: bool,
) -> None:
    vehicle = Vehicle(
        id=vehicle_id,
        code=code.strip(),
        vehicle_type=VehicleType(vehicle_type),
        pallet_capacity=pallet_capacity,
        weight_capacity_kg=weight_capacity_kg,
        is_active=is_active,
        is_placeholder=False,
    )
    with session_scope() as session:
        repo = VehicleRepository(session)
        if vehicle_id is None:
            repo.add(vehicle)
        else:
            repo.update(vehicle)


def _locations_to_rows(locations: list[Location]) -> list[dict[str, object]]:
    return [
        {
            "key": loc.location_key(),
            "name": loc.name,
            "city": loc.city or "",
            "country": loc.country or "",
            "postal_code": loc.postal_code or "",
            "latitude": loc.latitude,
            "longitude": loc.longitude,
        }
        for loc in locations
    ]


def _load_locations() -> list[Location]:
    with session_scope() as session:
        return list_locations(session)


def _save_location(**kwargs: object) -> None:
    with session_scope() as session:
        upsert_location(
            session,
            name=str(kwargs["name"]),
            city=str(kwargs.get("city") or "") or None,
            country=str(kwargs.get("country") or "") or None,
            postal_code=str(kwargs.get("postal_code") or "") or None,
            latitude=float(kwargs["latitude"]),  # type: ignore[arg-type]
            longitude=float(kwargs["longitude"]),  # type: ignore[arg-type]
        )


def _delete_location_job(name: str, city: str, country: str, postal: str) -> None:
    with session_scope() as session:
        delete_location(
            session,
            name=name,
            city=city or None,
            country=country or None,
            postal_code=postal or None,
        )


def _seed_locations_job() -> int:
    with session_scope() as session:
        return seed_location_coords(session)


def _apply_coords_job() -> int:
    with session_scope() as session:
        return apply_coords_to_existing_orders(session)


def _save_params_job(updates: dict, username: str):
    with session_scope() as session:
        return save_runtime_overrides(updates, session=session, username=username)


PARAM_LABELS_PL = {
    "depot_latitude": "Szerokość geograficzna magazynu",
    "depot_longitude": "Długość geograficzna magazynu",
    "min_fill_ratio": "Min. zapełnienie (0-1)",
    "max_drops_per_route": "Maks. punktów rozładunku",
    "solver_time_limit_s": "Limit czasu planowania [s]",
    "solver_seed": "Ziarno losowości (powtarzalność planów)",
    "default_delivery_days": "Domyślny termin dostawy [dni]",
    "cost_per_km": "Stawka €/km",
    "storage_cost_per_pallet_day": "Koszt magazynu €/paleta/dzień",
    "ltl_cost_multiplier": "Mnożnik drobnicy (LTL)",
    "buffer_savings_threshold": "Próg oszczędności bufora (0-1)",
    "max_buffer_days": "Maks. dni buforowania",
    "planning_date": "Dzień planowania (symulacja)",
    "ship_lead_days": "Wyjazd przed terminem [dni]",
    "warehouse_capacity_kg": "Pojemność magazynu [kg]",
    "upload_max_mb": "Limit uploadu Excel [MB]",
    "backup_keep": "Ile kopii zapasowych trzymać",
    "backup_hour": "Godzina nocnej kopii",
    "backup_minute": "Minuta nocnej kopii",
}


@ui.page("/settings")
async def settings_page() -> None:
    username = app.storage.user.get("username", "unknown")
    with page_frame("Ustawienia"):
        ops_page_header(
            "Ustawienia",
            "Flota, lokalizacje i parametry biznesowe.",
        )
        with ui.tabs().classes("w-full") as tabs:
            tab_fleet = ui.tab("Flota")
            tab_locations = ui.tab("Lokalizacje")
            tab_params = ui.tab("Parametry")
        with ui.tab_panels(tabs, value=tab_fleet).classes("w-full"):
            with ui.tab_panel(tab_fleet):
                with ui.element("div").classes("cd-ops-hero w-full mb-2"):
                    ui.label("Flota pojazdów").classes("font-bold")
                    ui.label(
                        "Ustaw liczbę aktywnych pojazdów według typu (bus, ciężarówka, plandeka). "
                        "Pojemności i kg/paleta pochodzą ze słownika floty. "
                        "Pojazdy z zatwierdzoną trasą nie są dezaktywowane."
                    ).classes("text-sm text-gray-700")

                type_overview = await run.io_bound(_load_fleet_type_overview)
                type_inputs: dict[str, object] = {}
                with ui.row().classes("w-full gap-4 flex-wrap mb-2"):
                    for row in type_overview:
                        vtype = str(row["vehicle_type"])
                        with (
                            ui.column().classes("cd-ops-panel gap-1 p-3").style("min-width: 220px")
                        ):
                            ui.label(vtype.upper()).classes("font-bold")
                            ui.label(
                                f"Palety: {row['pallet_capacity']} · "
                                f"Kg: {row['weight_capacity_kg']} · "
                                f"kg/paleta: {row['kg_per_pallet']}"
                            ).classes("text-xs text-gray-600")
                            ui.label(
                                f"Aktywne: {row['active_count']} · Zajęte: {row['busy_count']}"
                            ).classes("text-xs")
                            type_inputs[vtype] = ui.number(
                                "Liczba aktywnych",
                                value=int(row["active_count"]),
                                min=0,
                                precision=0,
                            ).classes("w-40")

                async def on_sync_type_counts() -> None:
                    messages: list[str] = []
                    for vtype, number_in in type_inputs.items():
                        target = int(number_in.value or 0)  # type: ignore[union-attr]
                        created, activated, deactivated, skipped = await run.io_bound(
                            _sync_fleet_type_job, vtype, target, username
                        )
                        messages.append(
                            f"{vtype}: +{created}/reakt.{activated}/-{deactivated}"
                            + (f" (pominięto zajęte: {skipped})" if skipped else "")
                        )
                    ui.notify(" · ".join(messages), type="positive")
                    await refresh_vehicles()
                    # refresh type labels by full page reload of overview numbers
                    refreshed = await run.io_bound(_load_fleet_type_overview)
                    for row in refreshed:
                        vtype = str(row["vehicle_type"])
                        if vtype in type_inputs:
                            type_inputs[vtype].value = int(row["active_count"])  # type: ignore[union-attr]

                with ui.row().classes("cd-toolbar mb-2"):
                    ui.button(
                        "Zastosuj liczby pojazdów",
                        icon="sync",
                        on_click=on_sync_type_counts,
                    ).props("color=primary")

                vehicles = await run.io_bound(_load_vehicles)
                fleet_host = ui.element("div").classes("cd-grid-host")
                with fleet_host:
                    grid = (
                        ui.aggrid(
                            {
                                "columnDefs": [
                                    selection_column(multiple=False),
                                    {"headerName": "ID", "field": "id", "width": 70},
                                    {"headerName": "Kod", "field": "code"},
                                    {"headerName": "Typ", "field": "vehicle_type"},
                                    {"headerName": "Palety", "field": "pallet_capacity"},
                                    {"headerName": "Kg", "field": "weight_capacity_kg"},
                                    {"headerName": "Aktywny", "field": "is_active"},
                                    {"headerName": "Zajęty", "field": "is_busy"},
                                ],
                                "rowData": _vehicles_to_rows(vehicles),
                                "rowSelection": "single",
                                "suppressRowClickSelection": True,
                                "domLayout": "normal",
                            }
                        )
                        .classes("w-full")
                        .style("height: 280px")
                    )
                editing_id: dict[str, int | None] = {"id": None}
                with ui.row().classes("w-full gap-2 flex-wrap items-end"):
                    code_in = ui.input("Kod pojazdu").classes("w-40")
                    type_in = ui.select(
                        ["bus", "truck", "curtain"], value="truck", label="Typ"
                    ).classes("w-40")
                    pallets_in = ui.number("Palety", value=33, min=1).classes("w-28")
                    weight_in = ui.number("Ładowność kg", value=24000, min=1).classes("w-36")
                    active_in = ui.checkbox("Aktywny", value=True)

                async def refresh_vehicles() -> None:
                    refreshed = await run.io_bound(_load_vehicles)
                    grid.options["rowData"] = _vehicles_to_rows(refreshed)
                    grid.update()

                async def on_save_vehicle() -> None:
                    await run.io_bound(
                        _save_vehicle,
                        vehicle_id=editing_id["id"],
                        code=str(code_in.value or ""),
                        vehicle_type=str(type_in.value or "truck"),
                        pallet_capacity=int(pallets_in.value or 0),
                        weight_capacity_kg=float(weight_in.value or 0),
                        is_active=bool(active_in.value),
                    )
                    editing_id["id"] = None
                    ui.notify("Zapisano pojazd.", type="positive")
                    await refresh_vehicles()

                async def on_edit_vehicle() -> None:
                    rows = await grid.get_selected_rows()
                    if not rows:
                        ui.notify("Zaznacz pojazd.", type="warning")
                        return
                    row = rows[0]
                    editing_id["id"] = int(row["id"])
                    code_in.value = str(row["code"])
                    type_in.value = str(row["vehicle_type"])
                    pallets_in.value = int(row["pallet_capacity"])
                    weight_in.value = float(row["weight_capacity_kg"])
                    active_in.value = row["is_active"] == "tak"

                with ui.row().classes("cd-toolbar"):
                    ui.button("Zapisz", on_click=on_save_vehicle).props("color=primary")
                    ui.button("Edytuj zaznaczony", on_click=on_edit_vehicle)
                    enlarge_grid_button(
                        grid,
                        fleet_host,
                        title="Flota",
                        compact_height="280px",
                    )

            with ui.tab_panel(tab_locations):
                with ui.element("div").classes("cd-ops-hero w-full mb-2"):
                    ui.label("Słownik współrzędnych").classes("font-bold")
                locations = await run.io_bound(_load_locations)
                loc_status = ui.label(f"Wpisów: {len(locations)}").classes("text-sm")
                loc_host = ui.element("div").classes("cd-grid-host")
                with loc_host:
                    loc_grid = (
                        ui.aggrid(
                            {
                                "columnDefs": [
                                    selection_column(multiple=False),
                                    {"headerName": "Nazwa", "field": "name"},
                                    {"headerName": "Miasto", "field": "city"},
                                    {"headerName": "Kraj", "field": "country"},
                                    {"headerName": "Lat", "field": "latitude"},
                                    {"headerName": "Lon", "field": "longitude"},
                                ],
                                "rowData": _locations_to_rows(locations),
                                "rowSelection": "single",
                                "suppressRowClickSelection": True,
                                "domLayout": "normal",
                            }
                        )
                        .classes("w-full")
                        .style("height: 280px")
                    )
                with ui.row().classes("w-full gap-2 flex-wrap items-end"):
                    loc_name = ui.input("Nazwa").classes("w-48")
                    loc_city = ui.input("Miasto").classes("w-32")
                    loc_country = ui.input("Kraj", value="FR").classes("w-20")
                    loc_postal = ui.input("Kod pocztowy").classes("w-28")
                    loc_lat = ui.number("Lat", value=50.0, format="%.5f").classes("w-32")
                    loc_lon = ui.number("Lon", value=4.0, format="%.5f").classes("w-32")

                async def refresh_locations() -> None:
                    refreshed = await run.io_bound(_load_locations)
                    loc_grid.options["rowData"] = _locations_to_rows(refreshed)
                    loc_grid.update()
                    loc_status.set_text(f"Wpisów: {len(refreshed)}")

                async def on_save_location() -> None:
                    if not loc_name.value:
                        ui.notify("Podaj nazwę.", type="warning")
                        return
                    await run.io_bound(
                        _save_location,
                        name=str(loc_name.value),
                        city=str(loc_city.value or ""),
                        country=str(loc_country.value or ""),
                        postal_code=str(loc_postal.value or ""),
                        latitude=float(loc_lat.value or 0),
                        longitude=float(loc_lon.value or 0),
                    )
                    ui.notify("Zapisano lokalizację.", type="positive")
                    await refresh_locations()

                async def on_delete_location() -> None:
                    rows = await loc_grid.get_selected_rows()
                    if not rows:
                        ui.notify("Zaznacz lokalizację.", type="warning")
                        return
                    row = rows[0]
                    await run.io_bound(
                        _delete_location_job,
                        str(row["name"]),
                        str(row.get("city") or ""),
                        str(row.get("country") or ""),
                        str(row.get("postal_code") or ""),
                    )
                    ui.notify("Usunięto.", type="positive")
                    await refresh_locations()

                async def on_load_seed() -> None:
                    n = await run.io_bound(_seed_locations_job)
                    ui.notify(f"Dodano ze słownika: {n}.", type="positive")
                    await refresh_locations()

                async def on_apply_coords() -> None:
                    n = await run.io_bound(_apply_coords_job)
                    ui.notify(f"Uzupełniono współrzędne w {n} zleceniach.", type="positive")

                with ui.row().classes("cd-toolbar flex-wrap"):
                    ui.button("Zapisz lokalizację", on_click=on_save_location).props(
                        "color=primary"
                    )
                    ui.button("Usuń zaznaczoną", on_click=on_delete_location).props(
                        "outline color=negative"
                    )
                    ui.button("Wczytaj słownik lokalizacji", on_click=on_load_seed).props("outline")
                    ui.button(
                        "Uzupełnij współrzędne w zleceniach",
                        on_click=on_apply_coords,
                    ).props("outline")
                    enlarge_grid_button(
                        loc_grid,
                        loc_host,
                        title="Lokalizacje",
                        compact_height="280px",
                    )

            with ui.tab_panel(tab_params):
                with ui.element("div").classes("cd-ops-hero w-full mb-2"):
                    ui.label("Parametry biznesowe").classes("font-bold")
                    ui.label(
                        "Zmiany zapisują się lokalnie i obowiązują od razu. "
                        "Hasła i adres serwera ustawia się poza tym ekranem."
                    ).classes("text-sm text-gray-700")
                snap = editable_settings_snapshot()
                fields: dict[str, ui.number] = {}
                groups = [
                    (
                        "Magazyn przeładunkowy",
                        ["depot_latitude", "depot_longitude"],
                    ),
                    (
                        "Planowanie",
                        [
                            "min_fill_ratio",
                            "max_drops_per_route",
                            "solver_time_limit_s",
                            "solver_seed",
                            "default_delivery_days",
                            "ship_lead_days",
                            "warehouse_capacity_kg",
                        ],
                    ),
                    (
                        "Koszty i bufor",
                        [
                            "cost_per_km",
                            "storage_cost_per_pallet_day",
                            "ltl_cost_multiplier",
                            "buffer_savings_threshold",
                            "max_buffer_days",
                        ],
                    ),
                    (
                        "Operacje",
                        [
                            "upload_max_mb",
                            "backup_keep",
                            "backup_hour",
                            "backup_minute",
                        ],
                    ),
                ]
                for title, keys in groups:
                    ui.label(title).classes("font-medium mt-2")
                    with ui.row().classes("w-full flex-wrap gap-3"):
                        for key in keys:
                            fields[key] = ui.number(
                                PARAM_LABELS_PL.get(key, key),
                                value=float(snap[key]),
                                format="%.4g",
                            ).classes("w-56")
                ui.label("Zegar symulacji").classes("font-medium mt-2")
                planning_in = (
                    ui.input(
                        PARAM_LABELS_PL["planning_date"],
                        value=str(snap.get("planning_date") or ""),
                    )
                    .props("type=date")
                    .classes("w-56")
                )
                ui.label("Puste pole = prawdziwa data kalendarzowa.").classes(
                    "text-xs text-gray-600"
                )

                async def on_save_params() -> None:
                    updates = {key: float(widget.value or 0) for key, widget in fields.items()}
                    # ints
                    for key in (
                        "max_drops_per_route",
                        "solver_seed",
                        "default_delivery_days",
                        "max_buffer_days",
                        "ship_lead_days",
                        "upload_max_mb",
                        "backup_keep",
                        "backup_hour",
                        "backup_minute",
                    ):
                        if key in updates:
                            updates[key] = int(updates[key])
                    raw_date = str(planning_in.value or "").strip()
                    updates["planning_date"] = raw_date or None
                    await run.io_bound(_save_params_job, updates, username)
                    ui.notify("Zapisano parametry.", type="positive")

                ui.button("Zapisz parametry", icon="save", on_click=on_save_params).props(
                    "color=primary"
                ).classes("mt-3")
