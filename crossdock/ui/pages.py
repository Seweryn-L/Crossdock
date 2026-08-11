"""Application pages: dashboard, orders, plans, map, reports, warehouse, system, settings.

UI texts in Polish.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path

from nicegui import app, run, ui

from crossdock.config import get_settings
from crossdock.domain.models import Location, Order, Vehicle, VehicleType
from crossdock.services.app_settings import (
    editable_settings_snapshot,
    save_runtime_overrides,
)
from crossdock.services.backup import run_backup
from crossdock.services.buffering import accept_buffer_proposals, propose_buffering
from crossdock.services.dashboard import collect_dashboard
from crossdock.services.import_orders import ImportOrdersService
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
from crossdock.services.plan_view import PlanView, build_plan_view
from crossdock.services.planning import PlanningService
from crossdock.services.reports import ReportBundle, build_report, export_report_xlsx
from crossdock.services.system_status import collect_system_status
from crossdock.services.warehouse_queue import (
    dequeue_order,
    enqueue_many,
    enqueue_order,
    list_enqueue_candidates,
    list_queue,
    move_order,
    set_held,
)
from crossdock.storage.database import session_scope
from crossdock.storage.repositories import (
    AssignmentRepository,
    OrderRepository,
    VehicleRepository,
)
from crossdock.ui.labels import (
    buffer_action_pl,
    order_status_pl,
    plan_status_pl,
    queue_status_pl,
)
from crossdock.ui.layout import ops_page_header, page_frame


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


def _load_planning_context() -> dict[str, object]:
    with session_scope() as session:
        counts = order_counts(session)
        active_vehicles = VehicleRepository(session).list_active()
        latest = AssignmentRepository(session).get_latest_run()
        return {
            "total_orders": counts.total,
            "new_orders": counts.new_status,
            "eligible_orders": counts.new_with_weight,
            "active_vehicles": len(active_vehicles),
            "plan_status": latest.plan_status if latest is not None else None,
            "latest_run_id": latest.id if latest is not None else None,
            "total_distance_km": latest.total_distance_km if latest else None,
            "total_cost_eur": latest.total_cost_eur if latest else None,
        }


def _import_upload(path: Path, username: str) -> tuple[int, int, list[str]]:
    with session_scope() as session:
        report = ImportOrdersService(session).import_path(path, username=username)
    messages = [f"Wiersz {e.row_number}: {e.message}" for e in report.rejected]
    messages.extend(report.warnings)
    return report.accepted_count, len(report.rejected), messages


def _load_last_import_summary() -> str | None:
    with session_scope() as session:
        return collect_system_status(session).last_import_summary


def _load_dashboard():
    with session_scope() as session:
        return collect_dashboard(session)


def _load_latest_plan_view() -> PlanView:
    with session_scope() as session:
        return build_plan_view(session)


def _enqueue_staying_job(order_ids: list[int], username: str) -> int:
    with session_scope() as session:
        return enqueue_many(session, order_ids=order_ids, username=username)


def _run_plan_job(username: str) -> tuple[int, str, int, int, int, list[str]]:
    with session_scope() as session:
        outcome = PlanningService(session).run_plan(username=username)
    plan = outcome.plan
    return (
        outcome.run_id,
        plan.status,
        len(outcome.planned_order_ids),
        len(plan.assignment.unassigned_order_ids),
        len(plan.routing.unrouted_order_ids),
        list(plan.warnings),
    )


def _approve_plan_job(run_id: int, username: str) -> tuple[int, int]:
    with session_scope() as session:
        outcome = PlanningService(session).approve_plan(run_id=run_id, username=username)
    return outcome.run_id, len(outcome.approved_order_ids)


def _unlock_plan_job(run_id: int, username: str) -> tuple[int, int]:
    with session_scope() as session:
        outcome = PlanningService(session).unlock_plan(run_id=run_id, username=username)
    return outcome.run_id, len(outcome.reset_order_ids)


def _delete_plan_job(run_id: int, username: str) -> tuple[int, int]:
    with session_scope() as session:
        outcome = PlanningService(session).delete_plan(run_id=run_id, username=username)
    return outcome.run_id, len(outcome.reset_order_ids)


def _update_pallets_job(order_id: int, total: int, username: str):
    with session_scope() as session:
        return update_approved_pallets(
            session, order_id=order_id, total_pallets=total, username=username
        )


@ui.page("/")
async def dashboard_page() -> None:
    with page_frame("Pulpit"):
        snap = await run.io_bound(_load_dashboard)
        username = app.storage.user.get("username", "unknown")

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

        from crossdock.ui.ops_dashboard import render_ops_focus_dashboard

        render_ops_focus_dashboard(
            snap,
            on_enqueue_staying=on_enqueue_staying,
            open_map=open_map,
        )


@ui.page("/orders")
async def orders_page() -> None:
    username = app.storage.user.get("username", "unknown")

    with page_frame("Zlecenia"):
        ops_page_header(
            "Zlecenia",
            "Import z Excela i przegląd zleceń. Statusy w UI po polsku.",
        )
        session_import = app.storage.user.get("last_import")
        if isinstance(session_import, dict):
            tone = "cd-ops-hero" if int(session_import.get("rejected", 0)) == 0 else "cd-ops-panel"
            with ui.element("div").classes(f"w-full {tone}"):
                ui.label(
                    f"Ostatni import (sesja): przyjęto {session_import.get('accepted', 0)}, "
                    f"odrzucono {session_import.get('rejected', 0)} "
                    f"({session_import.get('at', '')})."
                ).classes("text-sm text-gray-700")
        else:
            last_import = await run.io_bound(_load_last_import_summary)
            if last_import:
                with ui.element("div").classes("w-full cd-ops-hero"):
                    ui.label(f"Ostatni import: {last_import}").classes("text-sm text-gray-700")

        error_box = ui.column().classes("w-full gap-1")

        with ui.element("div").classes("cd-ops-panel w-full gap-3"):
            status_label = ui.label("").classes("text-sm text-gray-700 font-medium")
            hint_label = ui.label("").classes("text-xs text-gray-500")

            with ui.row().classes("cd-toolbar w-full"):
                refresh_btn = ui.button("Odśwież", icon="refresh").props("outline")
                delete_selected_btn = ui.button("Usuń zaznaczone", icon="delete").props(
                    "outline color=negative"
                )
                delete_all_btn = ui.button("Usuń wszystkie", icon="delete_sweep").props(
                    "outline color=negative"
                )
                pallets_btn = ui.button("Zmień palety", icon="pallet").props("outline")
                pallets_btn.disable()
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

            ui.label(
                "Format: raport e2open (nagłówek w wierszu 3). "
                "Mapowanie: config/excel_column_mapping.json."
            ).classes("text-xs text-gray-400")

        grid = (
            ui.aggrid(
                {
                    "columnDefs": [
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
                    "domLayout": "normal",
                }
            )
            .classes("w-full")
            .style("height: 420px")
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
                hint_label.set_text(
                    "Brak zleceń — zaimportuj plik Excel, aby rozpocząć planowanie."
                )
                delete_all_btn.disable()
            else:
                hint_label.set_text(
                    "Import doda nowe zlecenia. Usuń zaznaczone w tabeli. "
                    "Zmień palety: dostępne po zatwierdzeniu planu; "
                    "zaznacz jedno zlecenie zatwierdzone."
                )
                delete_all_btn.enable()
            await sync_pallets_button()

        async def refresh_grid() -> None:
            orders = await run.io_bound(_load_orders)
            counts = await run.io_bound(_load_order_counts)
            grid.options["rowData"] = _orders_to_grid_rows(orders)
            grid.update()
            await sync_toolbar(counts)

        async def handle_upload(e: ui.events.UploadEventArguments) -> None:
            error_box.clear()
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

            def _write_and_import() -> tuple[int, int, list[str]]:
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    tmp.write(content)
                    tmp_path = Path(tmp.name)
                try:
                    return _import_upload(tmp_path, username)
                finally:
                    tmp_path.unlink(missing_ok=True)

            accepted, rejected, messages = await run.io_bound(_write_and_import)
            app.storage.user["last_import"] = {
                "accepted": accepted,
                "rejected": rejected,
                "at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            ui.notify(
                f"Import zakończony: przyjęto {accepted} zleceń, odrzucono {rejected} wierszy.",
                type="positive" if rejected == 0 else "warning",
            )
            with error_box:
                for msg in messages[:50]:
                    ui.label(msg).classes("text-sm text-red-600")
            await refresh_grid()
            ui.navigate.to("/orders")

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
            "Plany",
            "Generowanie i zatwierdzanie transportów całopojazdowych.",
        )
        with ui.element("div").classes("cd-ops-hero w-full"):
            ui.label("Plan transportów całopojazdowych").classes("font-bold")
            ui.label(
                "System proponuje pełne auta z cross-docku. "
                "Co nie weszło na trasę, traktuj jako towar zostający w magazynie — "
                "możesz wrzucić do kolejki na Magazynie. "
                f"(Maks. {settings.max_drops_per_route} punktów rozładunku / trasę · "
                f"{settings.cost_per_km:.2f} €/km — placeholder.)"
            ).classes("text-sm text-gray-700")

        ctx = await run.io_bound(_load_planning_context)
        staying_ids: list[int] = []

        with ui.element("div").classes("cd-ops-panel w-full"):
            stats_label = ui.label("").classes("text-sm text-gray-700 font-medium")
            summary_label = ui.label("").classes("text-sm text-gray-700")
            blocker_label = ui.label("").classes("text-sm text-red-700")
            with ui.row().classes("cd-toolbar w-full"):
                refresh_btn = ui.button("Odśwież", icon="refresh").props("outline")
                generate_btn = ui.button("Generuj plan", icon="auto_awesome").props("color=primary")
                approve_btn = ui.button("Zatwierdź plan", icon="check_circle").props(
                    "color=positive"
                )
                unlock_btn = ui.button("Odblokuj plan", icon="lock_open").props("outline")
                delete_plan_btn = ui.button("Usuń plan", icon="delete").props(
                    "outline color=negative"
                )
                map_btn = ui.button("Pokaż na mapie", icon="map").props("outline")
            hint_plan_label = ui.label(
                "Po zatwierdzeniu generowanie jest zablokowane — użyj Odblokuj / Usuń."
            ).classes("text-xs text-gray-500")
            result_label = ui.label("").classes("text-sm text-gray-600")
            warn_box = ui.column().classes("w-full gap-1")

        ui.label("Trasy pojazdów (do zatwierdzenia)").classes("text-sm font-medium mt-2")
        routes_grid = (
            ui.aggrid(
                {
                    "columnDefs": [
                        {"headerName": "Pojazd", "field": "vehicle", "filter": True},
                        {
                            "headerName": "Punkty rozładunku",
                            "field": "drop_count",
                            "sortable": True,
                        },
                        {"headerName": "Km", "field": "distance_km", "sortable": True},
                        {"headerName": "Koszt €", "field": "cost_eur", "sortable": True},
                    ],
                    "rowData": [],
                    "defaultColDef": {"sortable": True, "resizable": True},
                    "domLayout": "normal",
                }
            )
            .classes("w-full")
            .style("height: 160px")
        )

        riding_cols = [
            {"headerName": "Pojazd", "field": "vehicle", "filter": True},
            {"headerName": "Kolejność", "field": "sequence", "sortable": True, "width": 110},
            {"headerName": "Punkt rozładunku", "field": "drop_key", "filter": True},
            {"headerName": "Kod dostawy", "field": "delivery_code", "filter": True},
            {"headerName": "ID", "field": "order_id", "sortable": True, "width": 80},
            {"headerName": "Waga [kg]", "field": "weight_kg", "sortable": True},
            {"headerName": "Zapełnienie", "field": "fill_pct"},
        ]
        stay_cols = [
            {"headerName": "Kod dostawy", "field": "delivery_code", "filter": True},
            {"headerName": "ID", "field": "order_id", "sortable": True, "width": 80},
            {"headerName": "Waga [kg]", "field": "weight_kg", "sortable": True},
            {"headerName": "Powód", "field": "reason", "flex": 1},
        ]

        with ui.tabs().classes("w-full") as tabs:
            tab_riding = ui.tab("Jedzie")
            tab_staying = ui.tab("Zostaje w magazynie")
            tab_attention = ui.tab("Wymaga uwagi")
        with ui.tab_panels(tabs, value=tab_riding).classes("w-full"):
            with ui.tab_panel(tab_riding):
                riding_grid = (
                    ui.aggrid(
                        {
                            "columnDefs": riding_cols,
                            "rowData": [],
                            "defaultColDef": {"sortable": True, "resizable": True},
                            "domLayout": "normal",
                        }
                    )
                    .classes("w-full")
                    .style("height: 300px")
                )
            with ui.tab_panel(tab_staying):
                ui.label("Zlecenia bez miejsca w flocie — towar zostaje w hubie.").classes(
                    "text-sm text-gray-600 mb-1"
                )
                with ui.row().classes("cd-toolbar w-full mb-1"):
                    enqueue_staying_btn = ui.button(
                        "Dodaj zostające do kolejki magazynowej",
                        icon="playlist_add",
                    ).props("color=primary")
                    staying_empty = ui.label("Brak zleceń w tej kategorii.").classes(
                        "text-sm text-gray-500"
                    )
                staying_grid = (
                    ui.aggrid(
                        {
                            "columnDefs": stay_cols,
                            "rowData": [],
                            "defaultColDef": {"sortable": True, "resizable": True},
                            "domLayout": "normal",
                        }
                    )
                    .classes("w-full")
                    .style("height: 260px")
                )
            with ui.tab_panel(tab_attention):
                ui.label(
                    "Brak trasy: uzupełnij współrzędne w Ustawieniach, "
                    "zmniejsz liczbę punktów rozładunku albo wygeneruj plan ponownie."
                ).classes("text-sm text-gray-600 mb-1")
                attention_empty = ui.label("Brak zleceń w tej kategorii.").classes(
                    "text-sm text-gray-500"
                )
                attention_grid = (
                    ui.aggrid(
                        {
                            "columnDefs": stay_cols,
                            "rowData": [],
                            "defaultColDef": {"sortable": True, "resizable": True},
                            "domLayout": "normal",
                        }
                    )
                    .classes("w-full")
                    .style("height: 260px")
                )

        async def sync_planning_state(ctx_now: dict[str, object], result_text: str = "") -> None:
            stats_label.set_text(
                f"W bazie: {ctx_now['total_orders']} zleceń | "
                f"do planowania (nowe + waga): {ctx_now['eligible_orders']} | "
                f"aktywne pojazdy: {ctx_now['active_vehicles']}"
            )
            plan_status = ctx_now.get("plan_status")
            blockers: list[str] = []
            can_generate = True
            if int(ctx_now["eligible_orders"]) == 0:  # type: ignore[arg-type]
                blockers.append("brak zleceń „nowe” z wagą — wgraj Excel na Zleceniach")
                can_generate = False
            if int(ctx_now["active_vehicles"]) == 0:  # type: ignore[arg-type]
                blockers.append("brak aktywnych pojazdów — dodaj flotę w Ustawieniach")
                can_generate = False
            if plan_status == "approved":
                blockers.append("najnowszy plan jest zatwierdzony — użyj Odblokuj lub Usuń")
                can_generate = False
            if blockers and not can_generate:
                blocker_label.set_text("Nie można generować: " + "; ".join(blockers) + ".")
                generate_btn.disable()
            else:
                blocker_label.set_text("")
                generate_btn.enable()
            if plan_status == "draft" and ctx_now.get("latest_run_id") is not None:
                approve_btn.enable()
            else:
                approve_btn.disable()
            if plan_status == "approved" and ctx_now.get("latest_run_id") is not None:
                unlock_btn.enable()
            else:
                unlock_btn.disable()
            if ctx_now.get("latest_run_id") is not None:
                delete_plan_btn.enable()
                map_btn.enable()
            else:
                delete_plan_btn.disable()
                map_btn.disable()
            hint_plan_label.set_visibility(plan_status == "approved")
            if result_text:
                result_label.set_text(result_text)

        async def refresh_plan_view() -> None:
            nonlocal ctx, staying_ids
            ctx = await run.io_bound(_load_planning_context)
            view = await run.io_bound(_load_latest_plan_view)
            if view.summary is None:
                summary_label.set_text("Brak planu — wygeneruj plan po imporcie zleceń.")
                staying_ids = []
                enqueue_staying_btn.disable()
            else:
                summary_label.set_text(view.summary.to_polish())
                staying_ids = list(view.staying_order_ids)
                if staying_ids:
                    enqueue_staying_btn.enable()
                else:
                    enqueue_staying_btn.disable()
            routes_grid.options["rowData"] = view.routes
            routes_grid.update()
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
            ctx_now = await run.io_bound(_load_planning_context)
            if (
                int(ctx_now["eligible_orders"]) == 0  # type: ignore[arg-type]
                or int(ctx_now["active_vehicles"]) == 0  # type: ignore[arg-type]
                or ctx_now.get("plan_status") == "approved"
            ):
                await sync_planning_state(ctx_now)
                ui.notify(
                    "Brak danych lub plan zatwierdzony — nie można generować.",
                    type="warning",
                )
                return
            warn_box.clear()
            result_label.set_text("Trwa optymalizacja planu…")
            generate_btn.disable()
            approve_btn.disable()
            try:
                (
                    run_id,
                    _status,
                    planned,
                    unassigned,
                    unrouted,
                    warnings,
                ) = await run.cpu_bound(_run_plan_job, username)
            except Exception as exc:
                await refresh_plan_view()
                ui.notify(str(exc), type="negative")
                return
            await refresh_plan_view()
            result_label.set_text(
                f"Plan #{run_id} · jedzie={planned} · "
                f"zostaje={unassigned} · wymaga uwagi={unrouted}"
            )
            with warn_box:
                for msg in warnings[:30]:
                    ui.label(msg).classes("text-sm text-amber-800")
            ui.notify(
                f"Plan #{run_id}: jedzie {planned}, zostaje {unassigned}, wymaga uwagi {unrouted}.",
                type="positive" if unassigned == 0 and unrouted == 0 else "warning",
            )

        async def on_approve() -> None:
            ctx_now = await run.io_bound(_load_planning_context)
            run_id = ctx_now.get("latest_run_id")
            if run_id is None or ctx_now.get("plan_status") != "draft":
                ui.notify("Brak planu roboczego do zatwierdzenia.", type="warning")
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
                f"Zatwierdzono plan #{approved_run}: {count} zleceń.",
                type="positive",
            )

        async def on_unlock() -> None:
            ctx_now = await run.io_bound(_load_planning_context)
            run_id = ctx_now.get("latest_run_id")
            if run_id is None or ctx_now.get("plan_status") != "approved":
                ui.notify("Odblokować można tylko zatwierdzony plan.", type="warning")
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
            ctx_now = await run.io_bound(_load_planning_context)
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
                            deleted_run, count = await run.io_bound(
                                _delete_plan_job,
                                int(run_id),  # type: ignore[arg-type]
                                username,
                            )
                        except Exception as exc:
                            await refresh_plan_view()
                            ui.notify(str(exc), type="negative")
                            return
                        await refresh_plan_view()
                        ui.notify(
                            f"Usunięto plan #{deleted_run}: {count} zleceń → nowe.",
                            type="positive",
                        )

                    ui.button("Usuń plan", on_click=confirm).props("color=negative")
            dialog.open()

        async def on_show_map() -> None:
            ctx_now = await run.io_bound(_load_planning_context)
            run_id = ctx_now.get("latest_run_id")
            if run_id is None:
                ui.notify("Brak planu do wyświetlenia na mapie.", type="warning")
                return
            ui.navigate.to(f"/map?run_id={int(run_id)}")  # type: ignore[arg-type]

        refresh_btn.on_click(refresh_plan_view)
        generate_btn.on_click(on_generate)
        approve_btn.on_click(on_approve)
        unlock_btn.on_click(on_unlock)
        delete_plan_btn.on_click(on_delete_plan)
        map_btn.on_click(on_show_map)
        enqueue_staying_btn.on_click(on_enqueue_staying)
        await refresh_plan_view()


def _load_map_view(run_id: int | None) -> MapPlanView | None:
    with session_scope() as session:
        service = MapViewService(session)
        if run_id is not None:
            return service.build_for_run(run_id)
        return service.build_latest()


@ui.page("/map")
async def map_page(run_id: int | None = None) -> None:
    with page_frame("Mapa"):
        ops_page_header(
            "Mapa",
            "Trasy planu (haversine). Strzałki = kierunek jazdy od magazynu.",
        )
        view = await run.io_bound(_load_map_view, run_id)
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
                f"Plan #{view.run_id} · {plan_status_pl(view.plan_status)} · "
                f"pojazdów na mapie: {len(view.routes)}"
            ).classes("font-medium")
            ui.label("Linie proste (haversine). Strzałki = kierunek jazdy od magazynu.").classes(
                "text-xs text-gray-500"
            )

        with ui.row().classes("w-full gap-4 items-start flex-wrap"):
            with ui.column().classes("gap-2 min-w-[200px]"):
                ui.label("Legenda").classes("font-medium")
                for route in view.routes:
                    km = f"{route.distance_km:.1f} km" if route.distance_km is not None else "?"
                    with ui.row().classes("items-center gap-2"):
                        ui.element("div").style(
                            f"width:14px;height:14px;border-radius:2px;background:{route.color};"
                        )
                        ui.label(f"{route.vehicle_code} · {len(route.markers)} pkt · {km}").classes(
                            "text-sm"
                        )

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
                m.generic_layer(
                    name="polyline",
                    args=[
                        list(route.polyline),
                        {"color": route.color, "weight": 4, "opacity": 0.85},
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
            "Zapełnienie i oszczędności względem scenariusza 1 zlecenie = 1 pojazd.",
        )
        with ui.element("div").classes("cd-ops-hero w-full"):
            ui.label("Efektywność planu").classes("font-bold")
            ui.label(
                "Zapełnienie wagowe pojazdów oraz oszczędności względem "
                "scenariusza 1 zlecenie = 1 pojazd. Stawka za km z ustawień."
            ).classes("text-sm text-gray-700")

        summary = ui.label("").classes("text-sm")
        util_grid = (
            ui.aggrid(
                {
                    "columnDefs": [
                        {"headerName": "Pojazd", "field": "vehicle"},
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
            bundle = await run.io_bound(_load_report)
            if bundle is None:
                summary.set_text("Brak planu do raportu.")
                util_grid.options["rowData"] = []
                util_grid.update()
                return
            sav = bundle.savings
            summary.set_text(
                f"Plan #{bundle.run_id} ({plan_status_pl(bundle.plan_status)}) · "
                f"oszczędność {sav.savings_eur:.0f} € ({sav.savings_pct:.0f}%)"
            )
            util_grid.options["rowData"] = [
                {
                    "vehicle": r.vehicle_code,
                    "drops": r.drop_count,
                    "fill": (round(r.fill_ratio * 100, 1) if r.fill_ratio is not None else "?"),
                    "km": round(r.distance_km, 1),
                    "cost": round(r.cost_eur, 2),
                }
                for r in bundle.utilization
            ]
            util_grid.update()

        async def on_download() -> None:
            data = await run.io_bound(_export_report_bytes)
            if data is None:
                ui.notify("Brak raportu do pobrania.", type="warning")
                return
            ui.download(data, "raport_crossdock.xlsx")

        with ui.row().classes("cd-toolbar"):
            ui.button("Odśwież", on_click=refresh_report).props("outline")
            ui.button("Pobierz Excel", icon="download", on_click=on_download).props("color=primary")
        await refresh_report()


def _load_report() -> ReportBundle | None:
    with session_scope() as session:
        return build_report(session)


def _export_report_bytes() -> bytes | None:
    with session_scope() as session:
        bundle = build_report(session)
        if bundle is None:
            return None
        return export_report_xlsx(bundle)


@ui.page("/warehouse")
async def warehouse_page() -> None:
    username = app.storage.user.get("username", "unknown")
    with page_frame("Magazyn"):
        ops_page_header(
            "Magazyn",
            "Kolejka priorytetowa wydań i propozycja buforowania kosztowego.",
        )
        with ui.element("div").classes("cd-ops-hero w-full"):
            ui.label("Kolejka magazynowa").classes("font-bold")
            ui.label(
                "Ręczny priorytet wydań (całe zlecenia). "
                "Poniżej: propozycja buforowania kosztowego."
            ).classes("text-sm text-gray-700")

        ui.label("Dostępne zlecenia (nowe)").classes("text-sm font-medium")
        candidates_grid = (
            ui.aggrid(
                {
                    "columnDefs": [
                        {"headerName": "ID", "field": "order_id", "width": 80},
                        {"headerName": "Kod", "field": "delivery_code", "filter": True},
                        {"headerName": "Miasto", "field": "city", "filter": True},
                        {"headerName": "Waga [kg]", "field": "weight_kg", "sortable": True},
                    ],
                    "rowData": [],
                    "rowSelection": "multiple",
                    "domLayout": "normal",
                }
            )
            .classes("w-full")
            .style("height: 200px")
        )
        with ui.row().classes("cd-toolbar"):
            enqueue_btn = ui.button("Dodaj do kolejki", icon="playlist_add").props("color=primary")
            candidates_empty = ui.label("Brak dostępnych zleceń „nowe” poza kolejką.").classes(
                "text-sm text-gray-500"
            )

        ui.label("Kolejka").classes("text-sm font-medium mt-2")
        grid = (
            ui.aggrid(
                {
                    "columnDefs": [
                        {"headerName": "Poz.", "field": "position", "width": 70},
                        {"headerName": "Kod", "field": "delivery_code", "filter": True},
                        {"headerName": "Miasto", "field": "city"},
                        {"headerName": "Waga [kg]", "field": "weight_kg"},
                        {"headerName": "Status", "field": "status"},
                        {"headerName": "ID", "field": "order_id", "width": 80},
                    ],
                    "rowData": [],
                    "rowSelection": "single",
                    "domLayout": "normal",
                }
            )
            .classes("w-full")
            .style("height: 240px")
        )
        queue_empty = ui.label(
            "Brak pozycji — dodaj zlecenie z listy powyżej lub z Planów."
        ).classes("text-sm text-gray-500")

        async def refresh_all() -> None:
            candidates, entries = await run.io_bound(_load_warehouse_view)
            candidates_grid.options["rowData"] = [
                {
                    "order_id": e.order_id,
                    "delivery_code": e.delivery_code,
                    "city": e.city,
                    "weight_kg": (round(e.weight_kg, 1) if e.weight_kg is not None else "?"),
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
                    "status": queue_status_pl(e.status),
                    "order_id": e.order_id,
                }
                for e in entries
            ]
            grid.update()
            queue_empty.set_visibility(len(entries) == 0)

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

        with ui.row().classes("cd-toolbar"):
            enqueue_btn.on_click(on_enqueue_selected)
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
            ui.button("Odśwież", on_click=refresh_all).props("flat")

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

        ui.label("Propozycja buforowania").classes("text-sm font-medium mt-3")
        buffer_summary = ui.label("").classes("text-sm text-gray-700")
        buffer_decisions: dict[int, object] = {}
        buffer_grid = (
            ui.aggrid(
                {
                    "columnDefs": [
                        {"headerName": "Kod", "field": "delivery_code"},
                        {"headerName": "ID", "field": "order_id", "width": 80},
                        {"headerName": "Decyzja", "field": "action"},
                        {"headerName": "Dni", "field": "buffer_days"},
                        {"headerName": "Oszczędność %", "field": "savings_pct"},
                    ],
                    "rowData": [],
                    "rowSelection": "multiple",
                    "domLayout": "normal",
                }
            )
            .classes("w-full")
            .style("height: 220px")
        )

        async def refresh_buffer() -> None:
            nonlocal buffer_decisions
            try:
                bundle = await run.io_bound(_propose_buffer_job, username)
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

        with ui.row().classes("cd-toolbar"):
            ui.button("Odśwież propozycję", icon="calculate", on_click=refresh_buffer).props(
                "outline"
            )
            ui.button("Akceptuj zaznaczone", icon="check", on_click=on_accept_buffer).props(
                "color=primary"
            )

        await refresh_all()
        await refresh_buffer()


def _load_warehouse_view():
    with session_scope() as session:
        return list_enqueue_candidates(session), list_queue(session)


def _propose_buffer_job(username: str):
    with session_scope() as session:
        return propose_buffering(session, username=username)


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
            ui.label("Podgląd bazy, planu, dysku, kopii zapasowej i ogona logów.").classes(
                "text-sm text-gray-700"
            )
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
            with log_box:
                ui.label("Ogon logu:").classes("text-sm font-medium font-sans")
                for line in st.log_tail or ("(brak plików logów)",):
                    ui.label(line)

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

        with ui.row().classes("cd-toolbar"):
            ui.button("Odśwież", icon="refresh", on_click=refresh_status).props("outline")
            ui.button("Utwórz kopię teraz", icon="backup", on_click=on_backup_now).props(
                "color=primary"
            )
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
        }
        for v in vehicles
    ]


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
    "depot_latitude": "Szerokość magazynu (lat)",
    "depot_longitude": "Długość magazynu (lon)",
    "min_fill_ratio": "Min. zapełnienie (0-1)",
    "max_drops_per_route": "Maks. punktów rozładunku",
    "solver_time_limit_s": "Limit czasu solvera [s]",
    "solver_seed": "Ziarno solvera",
    "default_delivery_days": "Domyślny termin dostawy [dni]",
    "cost_per_km": "Stawka €/km",
    "storage_cost_per_pallet_day": "Koszt magazynu €/paleta/dzień",
    "ltl_cost_multiplier": "Mnożnik drobnicy (LTL)",
    "buffer_savings_threshold": "Próg oszczędności bufora (0-1)",
    "max_buffer_days": "Maks. dni buforowania",
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
            "Flota, lokalizacje i parametry biznesowe (bez sekretów / host / port).",
        )
        with ui.tabs().classes("w-full") as tabs:
            tab_fleet = ui.tab("Flota")
            tab_locations = ui.tab("Lokalizacje")
            tab_params = ui.tab("Parametry")
        with ui.tab_panels(tabs, value=tab_fleet).classes("w-full"):
            with ui.tab_panel(tab_fleet):
                with ui.element("div").classes("cd-ops-hero w-full mb-2"):
                    ui.label("Flota pojazdów").classes("font-bold")
                vehicles = await run.io_bound(_load_vehicles)
                grid = (
                    ui.aggrid(
                        {
                            "columnDefs": [
                                {"headerName": "ID", "field": "id", "width": 70},
                                {"headerName": "Kod", "field": "code"},
                                {"headerName": "Typ", "field": "vehicle_type"},
                                {"headerName": "Palety", "field": "pallet_capacity"},
                                {"headerName": "Kg", "field": "weight_capacity_kg"},
                                {"headerName": "Aktywny", "field": "is_active"},
                            ],
                            "rowData": _vehicles_to_rows(vehicles),
                            "rowSelection": "single",
                            "domLayout": "normal",
                        }
                    )
                    .classes("w-full")
                    .style("height: 280px")
                )
                editing_id: dict[str, int | None] = {"id": None}
                with ui.row().classes("w-full gap-2 flex-wrap items-end"):
                    code_in = ui.input("Kod pojazdu").classes("w-40")
                    type_in = ui.select(["truck", "van"], value="truck", label="Typ").classes(
                        "w-32"
                    )
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

            with ui.tab_panel(tab_locations):
                with ui.element("div").classes("cd-ops-hero w-full mb-2"):
                    ui.label("Słownik współrzędnych").classes("font-bold")
                locations = await run.io_bound(_load_locations)
                loc_status = ui.label(f"Wpisów: {len(locations)}").classes("text-sm")
                loc_grid = (
                    ui.aggrid(
                        {
                            "columnDefs": [
                                {"headerName": "Nazwa", "field": "name"},
                                {"headerName": "Miasto", "field": "city"},
                                {"headerName": "Kraj", "field": "country"},
                                {"headerName": "Lat", "field": "latitude"},
                                {"headerName": "Lon", "field": "longitude"},
                            ],
                            "rowData": _locations_to_rows(locations),
                            "rowSelection": "single",
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
                    ui.notify(f"Dodano z seeda: {n}.", type="positive")
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
                    ui.button("Wczytaj seed", on_click=on_load_seed).props("outline")
                    ui.button("Uzupełnij coords w zleceniach", on_click=on_apply_coords).props(
                        "outline"
                    )

            with ui.tab_panel(tab_params):
                with ui.element("div").classes("cd-ops-hero w-full mb-2"):
                    ui.label("Parametry biznesowe").classes("font-bold")
                    ui.label(
                        "Zapis w data/runtime_settings.json (nadpisuje .env). Bez sekretów i hosta."
                    ).classes("text-sm text-gray-700")
                snap = editable_settings_snapshot()
                fields: dict[str, ui.number] = {}
                groups = [
                    (
                        "Magazyn (depot)",
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

                async def on_save_params() -> None:
                    updates = {key: float(widget.value or 0) for key, widget in fields.items()}
                    # ints
                    for key in (
                        "max_drops_per_route",
                        "solver_seed",
                        "default_delivery_days",
                        "max_buffer_days",
                        "upload_max_mb",
                        "backup_keep",
                        "backup_hour",
                        "backup_minute",
                    ):
                        updates[key] = int(updates[key])
                    await run.io_bound(_save_params_job, updates, username)
                    ui.notify("Zapisano parametry.", type="positive")

                ui.button("Zapisz parametry", icon="save", on_click=on_save_params).props(
                    "color=primary"
                ).classes("mt-3")
