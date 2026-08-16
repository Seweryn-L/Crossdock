"""Dashboard KPI aggregator for the home page."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from crossdock.domain.models import OrderStatus
from crossdock.services.plan_view import build_plan_view
from crossdock.services.system_status import collect_system_status
from crossdock.services.warehouse_queue import list_queue
from crossdock.storage.repositories import AssignmentRepository, OrderRepository
from crossdock.storage.tables import AssignmentItemRow
from crossdock.text_pl import format_plan_label, plan_status_pl


@dataclass(frozen=True)
class InProgressRoute:
    run_id: int
    vehicle_id: int
    vehicle_code: str
    order_count: int
    distance_km: float
    drops_summary: str


@dataclass(frozen=True)
class DashboardSnapshot:
    total_orders: int
    new_orders: int
    planned_orders: int
    approved_orders: int
    latest_plan_id: int | None
    latest_plan_status_pl: str | None
    plan_label: str | None
    plan_options: tuple[tuple[int, str], ...]
    riding: int
    staying: int
    attention: int
    queue_count: int
    last_import_summary: str | None
    staying_order_ids: tuple[int, ...]
    in_progress_routes: tuple[InProgressRoute, ...]


def _drop_label(item: AssignmentItemRow) -> str:
    raw = (item.drop_key or "").strip()
    if raw:
        parts = raw.split("|")
        head = parts[0].strip() if parts else ""
        if head:
            try:
                float(head)
            except ValueError:
                return head
    return (item.delivery_code or "").strip() or "?"


def _drops_summary(items: list[AssignmentItemRow]) -> str:
    labels: list[str] = []
    seen: set[str] = set()
    for item in sorted(items, key=lambda row: (row.sequence is None, row.sequence or 0)):
        label = _drop_label(item)
        if label in seen:
            continue
        seen.add(label)
        labels.append(label)
    if not labels:
        return "—"
    if len(labels) <= 4:
        return ", ".join(labels)
    return ", ".join(labels[:4]) + "…"


def list_in_progress_routes(session: Session, run_id: int | None) -> tuple[InProgressRoute, ...]:
    """Approved (not completed) routes of the active plan — vehicles still on the road."""
    if run_id is None:
        return ()
    repo = AssignmentRepository(session)
    run = repo.get_run(run_id)
    if run is None:
        return ()
    items = repo.list_items_for_run(run.id)
    by_vehicle: dict[int, list[AssignmentItemRow]] = {}
    for item in items:
        if item.vehicle_id is None:
            continue
        if item.sequence is None or item.vehicle_code in {"UNASSIGNED", "UNROUTED"}:
            continue
        by_vehicle.setdefault(item.vehicle_id, []).append(item)

    out: list[InProgressRoute] = []
    for route in repo.list_routes_for_run(run.id):
        if route.route_status != "approved" or route.vehicle_id is None:
            continue
        route_items = by_vehicle.get(route.vehicle_id, [])
        out.append(
            InProgressRoute(
                run_id=run.id,
                vehicle_id=route.vehicle_id,
                vehicle_code=route.vehicle_code,
                order_count=len(route_items),
                distance_km=float(route.distance_km),
                drops_summary=_drops_summary(route_items),
            )
        )
    return tuple(out)


def collect_dashboard(session: Session, *, run_id: int | None = None) -> DashboardSnapshot:
    orders = OrderRepository(session)
    total = orders.count()
    new_n = len(orders.list_by_status(OrderStatus.NEW))
    planned_n = len(orders.list_by_status(OrderStatus.PLANNED))
    approved_n = len(orders.list_by_status(OrderStatus.APPROVED))
    repo = AssignmentRepository(session)
    resolved = repo.resolve_run_id(run_id)
    view = build_plan_view(session, run_id=resolved)
    status = collect_system_status(session)
    queue_count = len(list_queue(session))

    plan_id = view.summary.run_id if view.summary else None
    plan_status = view.summary.plan_status if view.summary else None
    plan_status_display = plan_status_pl(plan_status) if plan_status else None
    plan_label = view.summary.label if view.summary else None
    plan_options = tuple(
        (
            row.id,
            format_plan_label(
                run_id=row.id,
                display_name=row.display_name,
                plan_status=row.plan_status,
                created_at=row.created_at,
            ),
        )
        for row in repo.list_recent_runs(limit=30)
    )
    return DashboardSnapshot(
        total_orders=total,
        new_orders=new_n,
        planned_orders=planned_n,
        approved_orders=approved_n,
        latest_plan_id=plan_id,
        latest_plan_status_pl=plan_status_display,
        plan_label=plan_label,
        plan_options=plan_options,
        riding=view.summary.riding if view.summary else 0,
        staying=view.summary.staying if view.summary else 0,
        attention=view.summary.attention if view.summary else 0,
        queue_count=queue_count,
        last_import_summary=status.last_import_summary,
        staying_order_ids=view.staying_order_ids if view.summary else (),
        in_progress_routes=list_in_progress_routes(session, plan_id),
    )
