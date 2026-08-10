"""Application pages: dashboard, orders (import + grid), fleet settings.

UI texts in Polish. Placeholders remain for plans/map/reports (T3-T6).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from nicegui import app, run, ui

from crossdock.config import get_settings
from crossdock.domain.models import Order, Vehicle, VehicleType
from crossdock.services.import_orders import ImportOrdersService
from crossdock.services.planning import PlanningService
from crossdock.storage.database import session_scope
from crossdock.storage.repositories import (
    AssignmentRepository,
    OrderRepository,
    VehicleRepository,
)
from crossdock.ui.layout import page_frame


def _placeholder(title: str, description: str) -> None:
    with page_frame(title), ui.card().classes("w-full max-w-3xl p-8 items-center"):
        ui.icon("construction").classes("text-6xl text-gray-400")
        ui.label(title).classes("text-xl font-bold")
        ui.label("W przygotowaniu").classes("text-sm uppercase text-gray-400")
        ui.label(description).classes("text-gray-600 text-center")


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
                "status": order.status.value,
                "shipments": len(order.shipments),
                "pallets": order.total_pallets if order.total_pallets is not None else "—",
                "weight_kg": (
                    round(order.total_weight_kg, 1) if order.total_weight_kg is not None else "—"
                ),
            }
        )
    return rows


def _load_orders() -> list[Order]:
    with session_scope() as session:
        return OrderRepository(session).list_all()


def _import_upload(path: Path, username: str) -> tuple[int, int, list[str]]:
    with session_scope() as session:
        report = ImportOrdersService(session).import_path(path, username=username)
    messages = [f"Wiersz {e.row_number}: {e.message}" for e in report.rejected]
    messages.extend(report.warnings)
    return report.accepted_count, len(report.rejected), messages


@ui.page("/")
def dashboard_page() -> None:
    with session_scope() as session:
        order_count = OrderRepository(session).count()
        vehicle_count = VehicleRepository(session).count()

    with page_frame("Pulpit"):
        with ui.card().classes("w-full max-w-3xl p-6"):
            ui.label("Witaj w systemie Crossdock").classes("text-2xl font-bold")
            ui.label(
                "System optymalizacji cross-dockingu: import zleceń, planowanie "
                "transportów FTL, wizualizacja tras i raporty."
            ).classes("text-gray-600")
        with ui.card().classes("w-full max-w-3xl p-6"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("info").classes("text-blue-500")
                ui.label("Status danych").classes("font-bold")
            if order_count == 0:
                ui.label(
                    "Brak zaimportowanych zleceń — przejdź do Zlecenia, aby wgrać plik Excel."
                ).classes("text-gray-600")
            else:
                ui.label(f"Zlecenia w bazie: {order_count}").classes("text-gray-600")
            ui.label(f"Pojazdy we flocie: {vehicle_count}").classes("text-gray-600")


@ui.page("/orders")
async def orders_page() -> None:
    username = app.storage.user.get("username", "unknown")

    with page_frame("Zlecenia"):
        status_label = ui.label("").classes("text-sm text-gray-600")
        error_box = ui.column().classes("w-full gap-1")

        orders = await run.io_bound(_load_orders)
        grid = ui.aggrid(
            {
                "columnDefs": [
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
                "rowData": _orders_to_grid_rows(orders),
                "defaultColDef": {"sortable": True, "resizable": True},
                "domLayout": "autoHeight",
            }
        ).classes("w-full")

        async def refresh_grid() -> None:
            refreshed = await run.io_bound(_load_orders)
            grid.options["rowData"] = _orders_to_grid_rows(refreshed)
            grid.update()
            status_label.set_text(f"Zlecenia w bazie: {len(refreshed)}")

        status_label.set_text(f"Zlecenia w bazie: {len(orders)}")

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
            ui.notify(
                f"Import zakończony: przyjęto {accepted} zleceń, odrzucono {rejected} wierszy.",
                type="positive" if rejected == 0 else "warning",
            )
            with error_box:
                for msg in messages[:50]:
                    ui.label(msg).classes("text-sm text-red-600")
                if len(messages) > 50:
                    ui.label(f"… i {len(messages) - 50} kolejnych.").classes("text-sm")
            await refresh_grid()

        ui.upload(
            label="Wgraj plik Excel (.xlsx)",
            on_upload=handle_upload,
            auto_upload=True,
            max_files=1,
        ).props('accept=".xlsx,.xls"').classes("w-full max-w-md")
        ui.label(
            "Oczekiwany format: raport e2open (przykładowe_dane_od_firmy.xlsx, "
            "nagłówek w wierszu 3). Mapowanie kolumn: config/excel_column_mapping.json."
        ).classes("text-xs text-gray-400")


def _load_latest_assignment_rows() -> tuple[list[dict[str, object]], str]:
    with session_scope() as session:
        repo = AssignmentRepository(session)
        run_id = repo.get_latest_run_id()
        if run_id is None:
            return [], "Brak wygenerowanego przydziału."
        items = repo.list_items_for_run(run_id)
        rows: list[dict[str, object]] = []
        for item in items:
            rows.append(
                {
                    "vehicle": item.vehicle_code,
                    "delivery_code": item.delivery_code,
                    "order_id": item.order_id,
                    "weight_kg": round(item.weight_kg, 1),
                    "fill_pct": (
                        f"{item.fill_ratio * 100:.0f}%" if item.fill_ratio is not None else "—"
                    ),
                }
            )
        return rows, f"Ostatni przydział (run #{run_id}), wierszy: {len(rows)}"


def _run_assignment_job(username: str) -> tuple[int, str, int, int, list[str]]:
    with session_scope() as session:
        outcome = PlanningService(session).run_assignment(username=username)
    result = outcome.result
    return (
        outcome.run_id,
        result.status,
        len(result.assigned_order_ids),
        len(result.unassigned_order_ids),
        list(result.warnings),
    )


@ui.page("/plans")
async def plans_page() -> None:
    username = app.storage.user.get("username", "unknown")
    with page_frame("Plany"):
        with ui.card().classes("w-full p-4 bg-amber-50"):
            ui.label("Przydział zleceń do pojazdów (T3)").classes("font-bold")
            ui.label(
                "Solver CP-SAT maksymalizuje zapełnienie wagowe (kg). "
                "Trasy i zatwierdzanie — tydzień 4. Flota może być placeholderem (W-03)."
            ).classes("text-sm text-gray-700")

        status_label = ui.label("").classes("text-sm text-gray-600")
        warn_box = ui.column().classes("w-full gap-1")

        rows, status_text = await run.io_bound(_load_latest_assignment_rows)
        status_label.set_text(status_text)
        grid = ui.aggrid(
            {
                "columnDefs": [
                    {"headerName": "Pojazd", "field": "vehicle", "filter": True},
                    {"headerName": "Kod dostawy", "field": "delivery_code", "filter": True},
                    {"headerName": "ID zlecenia", "field": "order_id", "sortable": True},
                    {"headerName": "Waga [kg]", "field": "weight_kg", "sortable": True},
                    {"headerName": "Zapełnienie", "field": "fill_pct"},
                ],
                "rowData": rows,
                "defaultColDef": {"sortable": True, "resizable": True},
                "domLayout": "autoHeight",
            }
        ).classes("w-full")

        async def on_generate() -> None:
            warn_box.clear()
            status_label.set_text("Trwa optymalizacja przydziału…")
            ui.notify("Uruchomiono solver (osobny proces).", type="info")
            run_id, status, assigned, unassigned, warnings = await run.cpu_bound(
                _run_assignment_job, username
            )
            refreshed, text = await run.io_bound(_load_latest_assignment_rows)
            grid.options["rowData"] = refreshed
            grid.update()
            status_label.set_text(
                f"{text} | status={status} | przydzielono={assigned} | bez pojazdu={unassigned}"
            )
            with warn_box:
                for msg in warnings[:30]:
                    ui.label(msg).classes("text-sm text-amber-800")
            ui.notify(
                f"Przydział #{run_id}: {assigned} zleceń na pojazdach, "
                f"{unassigned} nieprzydzielonych.",
                type="positive" if unassigned == 0 else "warning",
            )

        ui.button("Generuj przydział", on_click=on_generate).props("color=primary")


@ui.page("/map")
def map_page() -> None:
    _placeholder("Mapa", "Wizualizacja tras pojazdów na mapie (tydzień 5).")


@ui.page("/reports")
def reports_page() -> None:
    _placeholder("Raporty", "Raporty zapełnienia pojazdów i oszczędności (tydzień 6).")


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


@ui.page("/settings")
async def settings_page() -> None:
    with page_frame("Ustawienia"):
        with ui.card().classes("w-full p-4 bg-amber-50"):
            ui.label("Uwaga: parametry floty są tymczasowe").classes("font-bold")
            ui.label(
                "Brak tabeli floty od Martyny (W-03). Seed PLACEHOLDER_PENDING_MARTYNA — "
                "po dostarczeniu danych należy zastąpić pojemności "
                "(docs/otwarte_wejscia_zespolu.md)."
            ).classes("text-sm text-gray-700")

        vehicles = await run.io_bound(_load_vehicles)
        grid = ui.aggrid(
            {
                "columnDefs": [
                    {"headerName": "Kod", "field": "code", "filter": True},
                    {"headerName": "Typ", "field": "vehicle_type", "filter": True},
                    {"headerName": "Palety", "field": "pallet_capacity", "sortable": True},
                    {
                        "headerName": "Ładowność [kg]",
                        "field": "weight_capacity_kg",
                        "sortable": True,
                    },
                    {"headerName": "Aktywny", "field": "is_active"},
                    {"headerName": "Placeholder", "field": "is_placeholder"},
                ],
                "rowData": _vehicles_to_rows(vehicles),
                "defaultColDef": {"sortable": True, "resizable": True},
                "rowSelection": "single",
                "domLayout": "autoHeight",
            }
        ).classes("w-full")

        with ui.row().classes("w-full gap-4 items-end flex-wrap"):
            code_in = ui.input("Kod pojazdu").classes("w-40")
            type_in = ui.select(
                {t.value: t.value for t in VehicleType},
                label="Typ",
                value=VehicleType.TRUCK.value,
            ).classes("w-40")
            pallets_in = ui.number("Pojemność palet", value=20, min=1, precision=0).classes("w-40")
            weight_in = ui.number("Ładowność kg", value=12000, min=1).classes("w-40")
            active_in = ui.checkbox("Aktywny", value=True)
            editing_id: dict[str, int | None] = {"id": None}

            async def refresh() -> None:
                refreshed = await run.io_bound(_load_vehicles)
                grid.options["rowData"] = _vehicles_to_rows(refreshed)
                grid.update()

            async def on_save() -> None:
                if not code_in.value or not str(code_in.value).strip():
                    ui.notify("Podaj kod pojazdu.", type="warning")
                    return
                try:
                    await run.io_bound(
                        _save_vehicle,
                        vehicle_id=editing_id["id"],
                        code=str(code_in.value),
                        vehicle_type=str(type_in.value),
                        pallet_capacity=int(pallets_in.value or 0),
                        weight_capacity_kg=float(weight_in.value or 0),
                        is_active=bool(active_in.value),
                    )
                except Exception as exc:
                    ui.notify(f"Nie udało się zapisać: {exc}", type="negative")
                    return
                editing_id["id"] = None
                code_in.value = ""
                ui.notify("Zapisano pojazd.", type="positive")
                await refresh()

            async def on_edit() -> None:
                rows = await grid.get_selected_rows()
                if not rows:
                    ui.notify("Zaznacz pojazd w tabeli.", type="warning")
                    return
                row = rows[0]
                editing_id["id"] = int(row["id"])
                code_in.value = str(row["code"])
                type_in.value = str(row["vehicle_type"])
                pallets_in.value = int(row["pallet_capacity"])
                weight_in.value = float(row["weight_capacity_kg"])
                active_in.value = row["is_active"] == "tak"

            ui.button("Zapisz", on_click=on_save).props("color=primary")
            ui.button("Edytuj zaznaczony", on_click=on_edit)
