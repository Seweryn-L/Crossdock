"""Human-readable plan view: riding / staying / attention buckets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.orm import Session

from crossdock.config import Settings, get_settings
from crossdock.services.pallet_demand import cargo_table_pallets, demand_on_vehicle
from crossdock.storage.repositories import (
    AssignmentRepository,
    OrderRepository,
    VehicleRepository,
)
from crossdock.storage.tables import AssignmentItemRow

PlanBucket = Literal["riding", "staying", "attention"]

REASON_STAYING = "brak miejsca w flocie / nie wszedł do transportu całopojazdowego"
REASON_ATTENTION = "brak trasy (współrzędne lub limit punktów rozładunku)"
REASON_UNKNOWN = "nieznany stan"


@dataclass(frozen=True, slots=True)
class PlanSummary:
    run_id: int
    plan_status: str
    riding: int
    staying: int
    attention: int
    vehicles: int
    total_distance_km: float | None
    total_cost_eur: float | None

    def to_polish(self) -> str:
        from crossdock.text_pl import plan_status_pl

        km = f"{self.total_distance_km:.0f} km" if self.total_distance_km is not None else "—"
        cost = f"{self.total_cost_eur:.0f} €" if self.total_cost_eur is not None else "—"
        status = plan_status_pl(self.plan_status)
        return (
            f"Plan #{self.run_id} ({status}): "
            f"jedzie {self.riding} zleceń / {self.vehicles} pojazdy · "
            f"{km} · {cost} · "
            f"zostaje w magazynie {self.staying} · "
            f"wymaga uwagi {self.attention}."
        )


@dataclass(frozen=True, slots=True)
class PlanView:
    summary: PlanSummary | None
    routes: list[dict[str, object]]
    riding: list[dict[str, object]]
    staying: list[dict[str, object]]
    attention: list[dict[str, object]]
    staying_order_ids: tuple[int, ...]


def classify_item(*, vehicle_code: str, sequence: int | None) -> tuple[PlanBucket, str]:
    if sequence is not None and vehicle_code not in {"UNASSIGNED", "UNROUTED"}:
        return "riding", ""
    if vehicle_code == "UNASSIGNED":
        return "staying", REASON_STAYING
    if vehicle_code == "UNROUTED":
        return "attention", REASON_ATTENTION
    return "attention", REASON_UNKNOWN


def build_plan_view(session: Session, settings: Settings | None = None) -> PlanView:
    cfg = settings
    if cfg is None:
        try:
            cfg = get_settings()
        except Exception:
            cfg = None
    repo = AssignmentRepository(session)
    run = repo.get_latest_run()
    if run is None:
        return PlanView(
            summary=None,
            routes=[],
            riding=[],
            staying=[],
            attention=[],
            staying_order_ids=(),
        )

    items = repo.list_items_for_run(run.id)
    routes = repo.list_routes_for_run(run.id)
    orders = OrderRepository(session)
    vehicles = VehicleRepository(session)

    riding: list[dict[str, object]] = []
    staying: list[dict[str, object]] = []
    attention: list[dict[str, object]] = []
    staying_ids: list[int] = []
    pallets_by_vehicle: dict[str, int] = {}

    for item in items:
        bucket, reason = classify_item(vehicle_code=item.vehicle_code, sequence=item.sequence)
        order = orders.get_by_id(item.order_id)
        vehicle = vehicles.get_by_code(item.vehicle_code) if bucket == "riding" else None
        row = _item_to_row(item, reason, order=order, vehicle=vehicle, settings=cfg)
        if bucket == "riding":
            riding.append(row)
            raw = row.get("pallets")
            if isinstance(raw, int):
                pallets_by_vehicle[item.vehicle_code] = (
                    pallets_by_vehicle.get(item.vehicle_code, 0) + raw
                )
        elif bucket == "staying":
            staying.append(row)
            staying_ids.append(item.order_id)
        else:
            attention.append(row)

    route_rows: list[dict[str, object]] = []
    for route in routes:
        from crossdock.text_pl import route_status_pl

        status = route.route_status or "proposed"
        vehicle = vehicles.get_by_code(route.vehicle_code)
        used = pallets_by_vehicle.get(route.vehicle_code, 0)
        cap = vehicle.pallet_capacity if vehicle is not None else None
        fill = f"{used}/{cap}" if cap is not None else str(used)
        route_rows.append(
            {
                "vehicle_id": route.vehicle_id,
                "vehicle": route.vehicle_code,
                "drop_count": route.drop_count,
                "distance_km": round(route.distance_km, 1),
                "cost_eur": round(route.cost_eur, 2),
                "pallets": used,
                "pallet_fill": fill,
                "route_status": status,
                "route_status_pl": route_status_pl(status),
            }
        )
    known = {r.vehicle_code for r in routes}
    for code in {i.vehicle_code for i in items} - known - {"UNASSIGNED", "UNROUTED"}:
        route_rows.append(
            {
                "vehicle_id": None,
                "vehicle": code,
                "drop_count": 0,
                "distance_km": 0.0,
                "cost_eur": 0.0,
                "pallets": pallets_by_vehicle.get(code, 0),
                "pallet_fill": str(pallets_by_vehicle.get(code, 0)),
                "route_status": "proposed",
                "route_status_pl": "propozycja",
            }
        )

    vehicle_count = len({r["vehicle"] for r in route_rows})
    summary = PlanSummary(
        run_id=run.id,
        plan_status=run.plan_status,
        riding=len(riding),
        staying=len(staying),
        attention=len(attention),
        vehicles=vehicle_count,
        total_distance_km=run.total_distance_km,
        total_cost_eur=run.total_cost_eur,
    )
    return PlanView(
        summary=summary,
        routes=route_rows,
        riding=riding,
        staying=staying,
        attention=attention,
        staying_order_ids=tuple(staying_ids),
    )


def _item_to_row(
    item: AssignmentItemRow,
    reason: str,
    *,
    order: Any = None,
    vehicle: Any = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    pallets: int | str = "—"
    if order is not None and vehicle is not None:
        pallets = demand_on_vehicle(order, vehicle, settings)
    elif order is not None:
        shown = cargo_table_pallets(order)
        pallets = shown if shown is not None else "—"
    return {
        "vehicle": item.vehicle_code,
        "sequence": item.sequence if item.sequence is not None else "—",
        "drop_key": item.drop_key or "—",
        "delivery_code": item.delivery_code,
        "order_id": item.order_id,
        "weight_kg": round(item.weight_kg, 1),
        "pallets": pallets,
        "fill_pct": (f"{item.fill_ratio * 100:.0f}%" if item.fill_ratio is not None else "—"),
        "reason": reason or "—",
    }
