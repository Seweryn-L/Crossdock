"""Human-readable plan view: riding / staying / attention buckets."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

from sqlalchemy.orm import Session

from crossdock.config import Settings, effective_planning_date, get_settings
from crossdock.domain.sla import route_should_send, slack_days
from crossdock.storage.repositories import AssignmentRepository, OrderRepository, VehicleRepository
from crossdock.storage.tables import AssignmentItemRow, AssignmentRunRow
from crossdock.text_pl import format_plan_label
from crossdock.text_pl import route_status_pl as _route_status_pl

PlanBucket = Literal["riding", "staying", "attention"]

REASON_STAYING = "brak miejsca w flocie / nie wszedł do transportu całopojazdowego"
REASON_HOLDING = "czeka na dopełnienie (poniżej progu zapełnienia)"
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
    display_name: str | None = None
    created_at: datetime | None = None

    @property
    def label(self) -> str:
        return format_plan_label(
            run_id=self.run_id,
            display_name=self.display_name,
            plan_status=self.plan_status,
            created_at=self.created_at,
        )

    def to_polish(self) -> str:
        km = f"{self.total_distance_km:.0f} km" if self.total_distance_km is not None else "—"
        cost = f"{self.total_cost_eur:.0f} €" if self.total_cost_eur is not None else "—"
        return (
            f"{self.label}: "
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
    holding_order_ids: tuple[int, ...] = ()
    below_min_fill_count: int = 0
    min_fill_ratio: float = 0.90


@dataclass(frozen=True, slots=True)
class InTransitRoute:
    """Approved, not-yet-completed route of the active plan (warehouse / dashboard)."""

    vehicle_id: int
    vehicle_code: str
    order_count: int
    distance_km: float
    route_status: str
    drop_summary: str


def classify_item(*, vehicle_code: str, sequence: int | None) -> tuple[PlanBucket, str]:
    if sequence is not None and vehicle_code not in {"UNASSIGNED", "UNROUTED"}:
        return "riding", ""
    if vehicle_code == "UNASSIGNED":
        return "staying", REASON_STAYING
    if vehicle_code == "UNROUTED":
        return "attention", REASON_ATTENTION
    return "attention", REASON_UNKNOWN


def build_plan_view(
    session: Session,
    settings: Settings | None = None,
    *,
    run_id: int | None = None,
) -> PlanView:
    cfg = settings
    if cfg is None:
        try:
            cfg = get_settings()
        except Exception:
            cfg = None
    min_fill = cfg.min_fill_ratio if cfg is not None else 0.90

    repo = AssignmentRepository(session)
    vehicles = VehicleRepository(session)
    run = _resolve_run(repo, run_id)
    if run is None:
        return PlanView(
            summary=None,
            routes=[],
            riding=[],
            staying=[],
            attention=[],
            staying_order_ids=(),
            holding_order_ids=(),
            below_min_fill_count=0,
            min_fill_ratio=min_fill,
        )

    items = repo.list_items_for_run(run.id)
    routes = repo.list_routes_for_run(run.id)
    order_repo = OrderRepository(session)
    planning = effective_planning_date(cfg) if cfg is not None else date.today()
    lead = cfg.ship_lead_days if cfg is not None else 2
    capacity_kg = float(cfg.warehouse_capacity_kg) if cfg is not None else 0.0

    riding: list[dict[str, object]] = []
    staying: list[dict[str, object]] = []
    attention: list[dict[str, object]] = []
    staying_ids: list[int] = []
    weight_by_vehicle: dict[str, float] = {}
    orders_by_vehicle: dict[str, set[int]] = defaultdict(set)
    drops_by_vehicle: dict[str, list[str]] = defaultdict(list)
    slack_by_order: dict[int, int] = {}
    slack_by_vehicle: dict[str, list[int]] = defaultdict(list)

    for item in items:
        order = order_repo.get_by_id(item.order_id)
        if order is not None:
            slack_by_order[item.order_id] = slack_days(order.delivery_date, planning, lead)
        bucket, reason = classify_item(vehicle_code=item.vehicle_code, sequence=item.sequence)
        row = _item_to_row(item, reason, slack=slack_by_order.get(item.order_id))
        if bucket == "riding":
            riding.append(row)
            weight_by_vehicle[item.vehicle_code] = weight_by_vehicle.get(
                item.vehicle_code, 0.0
            ) + float(item.weight_kg)
            orders_by_vehicle[item.vehicle_code].add(item.order_id)
            if item.order_id in slack_by_order:
                slack_by_vehicle[item.vehicle_code].append(slack_by_order[item.order_id])
            if item.drop_key:
                drops_by_vehicle[item.vehicle_code].append(item.drop_key)
        elif bucket == "staying":
            staying.append(row)
            staying_ids.append(item.order_id)
        else:
            attention.append(row)

    route_rows: list[dict[str, object]] = []
    below_count = 0
    for route in routes:
        vehicle = vehicles.get_by_code(route.vehicle_code)
        used_kg = weight_by_vehicle.get(route.vehicle_code, 0.0)
        cap = vehicle.weight_capacity_kg if vehicle is not None else None
        fill: float | None = None
        if cap is not None and cap > 0:
            fill = used_kg / cap
        below = bool(fill is not None and fill < min_fill)
        if below:
            below_count += 1
        slacks = slack_by_vehicle.get(route.vehicle_code, [])
        send = route_should_send(fill_ratio=fill, min_fill_ratio=min_fill, slacks=slacks)
        unique_drops = list(dict.fromkeys(drops_by_vehicle.get(route.vehicle_code, [])))
        drop_summary = ", ".join(unique_drops[:3])
        if len(unique_drops) > 3:
            drop_summary = f"{drop_summary}…"
        min_slack = min(slacks) if slacks else None
        if send and min_slack is not None and min_slack <= 0:
            sla_label = "Ostatni dzień wyjazdu" if min_slack == 0 else "Spóźnione"
        elif send:
            sla_label = "Wyślij"
        else:
            sla_label = f"Czeka na dopełnienie ({round((fill or 0) * 100)}%)"
        route_rows.append(
            {
                "vehicle_id": route.vehicle_id,
                "vehicle": route.vehicle_code,
                "route_status": route.route_status,
                "route_status_pl": _route_status_pl(route.route_status),
                "drop_count": route.drop_count,
                "order_count": len(orders_by_vehicle.get(route.vehicle_code, ())),
                "drop_summary": drop_summary,
                "distance_km": round(route.distance_km, 1),
                "cost_eur": round(route.cost_eur, 2),
                "weight_fill_pct": round(fill * 100) if fill is not None else None,
                "below_min_fill": below,
                "disposition": "send" if send else "hold",
                "sla_label": sla_label,
                "min_slack": min_slack,
            }
        )
    known = {r.vehicle_code for r in routes}
    for code in {i.vehicle_code for i in items} - known - {"UNASSIGNED", "UNROUTED"}:
        route_rows.append(
            {
                "vehicle_id": None,
                "vehicle": code,
                "route_status": "proposed",
                "route_status_pl": _route_status_pl("proposed"),
                "drop_count": 0,
                "order_count": len(orders_by_vehicle.get(code, ())),
                "drop_summary": "",
                "distance_km": 0.0,
                "cost_eur": 0.0,
                "weight_fill_pct": None,
                "below_min_fill": False,
                "disposition": "send",
                "sla_label": "Wyślij",
                "min_slack": min(slack_by_vehicle.get(code, []), default=None),
            }
        )

    if capacity_kg > 0:
        holding_kg = sum(
            weight_by_vehicle.get(str(r["vehicle"]), 0.0)
            for r in route_rows
            if r.get("disposition") == "hold"
        )
        unassigned_kg = sum(
            float(item.weight_kg) for item in items if item.vehicle_code == "UNASSIGNED"
        )
        remaining = holding_kg + unassigned_kg
        if remaining > capacity_kg:
            hold_routes = [r for r in route_rows if r.get("disposition") == "hold"]
            hold_routes.sort(
                key=lambda r: r["min_slack"] if isinstance(r.get("min_slack"), int) else 10**9
            )
            for row in hold_routes:
                if remaining <= capacity_kg:
                    break
                row["disposition"] = "send"
                row["sla_label"] = "Wypychane z magazynu"
                remaining -= weight_by_vehicle.get(str(row["vehicle"]), 0.0)

    hold_codes = {str(r["vehicle"]) for r in route_rows if r.get("disposition") == "hold"}
    final_riding: list[dict[str, object]] = []
    holding_ids: list[int] = []
    for row in riding:
        code = str(row.get("vehicle") or "")
        if code in hold_codes:
            row["reason"] = REASON_HOLDING
            staying.append(row)
            holding_ids.append(int(row["order_id"]))  # type: ignore[arg-type]
        else:
            final_riding.append(row)
    riding = final_riding

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
        display_name=run.display_name,
        created_at=run.created_at,
    )
    return PlanView(
        summary=summary,
        routes=route_rows,
        riding=riding,
        staying=staying,
        attention=attention,
        staying_order_ids=tuple(staying_ids),
        holding_order_ids=tuple(holding_ids),
        below_min_fill_count=below_count,
        min_fill_ratio=min_fill,
    )


def _item_to_row(
    item: AssignmentItemRow, reason: str, *, slack: int | None = None
) -> dict[str, Any]:
    sla = "—"
    if slack is not None:
        if slack < 0:
            sla = "spóźnione"
        elif slack == 0:
            sla = "musi dziś"
        else:
            sla = f"może czekać {slack} dni"
    return {
        "vehicle": item.vehicle_code,
        "sequence": item.sequence if item.sequence is not None else "—",
        "drop_key": item.drop_key or "—",
        "delivery_code": item.delivery_code,
        "order_id": item.order_id,
        "weight_kg": round(item.weight_kg, 1),
        "fill_pct": (f"{item.fill_ratio * 100:.0f}%" if item.fill_ratio is not None else "—"),
        "reason": reason or "—",
        "slack_days": slack,
        "sla": sla,
    }


def _resolve_run(repo: AssignmentRepository, run_id: int | None) -> AssignmentRunRow | None:
    if run_id is not None:
        run = repo.get_run(run_id)
        if run is not None:
            return run
    return repo.get_latest_run()


def in_transit_route_from_row(row: dict[str, object]) -> InTransitRoute | None:
    if row.get("route_status") != "approved":
        return None
    raw_id = row.get("vehicle_id")
    if not isinstance(raw_id, int):
        return None
    raw_count = row.get("order_count")
    order_count = raw_count if isinstance(raw_count, int) else 0
    raw_km = row.get("distance_km")
    distance_km = float(raw_km) if isinstance(raw_km, (int, float)) else 0.0
    return InTransitRoute(
        vehicle_id=raw_id,
        vehicle_code=str(row.get("vehicle") or ""),
        order_count=order_count,
        distance_km=distance_km,
        route_status="approved",
        drop_summary=str(row.get("drop_summary") or ""),
    )


def list_in_transit_routes(
    session: Session,
    *,
    run_id: int | None = None,
) -> tuple[InTransitRoute, ...]:
    """Approved routes of the active plan that have not been completed yet."""
    view = build_plan_view(session, run_id=run_id)
    return tuple(
        route for row in view.routes if (route := in_transit_route_from_row(row)) is not None
    )
