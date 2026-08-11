"""Human-readable plan view: riding / staying / attention buckets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.orm import Session

from crossdock.storage.repositories import AssignmentRepository
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


def build_plan_view(session: Session) -> PlanView:
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

    riding: list[dict[str, object]] = []
    staying: list[dict[str, object]] = []
    attention: list[dict[str, object]] = []
    staying_ids: list[int] = []

    for item in items:
        bucket, reason = classify_item(vehicle_code=item.vehicle_code, sequence=item.sequence)
        row = _item_to_row(item, reason)
        if bucket == "riding":
            riding.append(row)
        elif bucket == "staying":
            staying.append(row)
            staying_ids.append(item.order_id)
        else:
            attention.append(row)

    route_rows: list[dict[str, object]] = [
        {
            "vehicle": route.vehicle_code,
            "drop_count": route.drop_count,
            "distance_km": round(route.distance_km, 1),
            "cost_eur": round(route.cost_eur, 2),
        }
        for route in routes
    ]
    known = {r.vehicle_code for r in routes}
    for code in {i.vehicle_code for i in items} - known - {"UNASSIGNED", "UNROUTED"}:
        route_rows.append({"vehicle": code, "drop_count": 0, "distance_km": 0.0, "cost_eur": 0.0})

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


def _item_to_row(item: AssignmentItemRow, reason: str) -> dict[str, Any]:
    return {
        "vehicle": item.vehicle_code,
        "sequence": item.sequence if item.sequence is not None else "—",
        "drop_key": item.drop_key or "—",
        "delivery_code": item.delivery_code,
        "order_id": item.order_id,
        "weight_kg": round(item.weight_kg, 1),
        "fill_pct": (f"{item.fill_ratio * 100:.0f}%" if item.fill_ratio is not None else "—"),
        "reason": reason or "—",
    }
