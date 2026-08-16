"""Dashboard KPI aggregator for the home page."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from crossdock.domain.models import OrderStatus
from crossdock.services.plan_view import build_plan_view
from crossdock.services.system_status import collect_system_status
from crossdock.services.warehouse_queue import list_queue
from crossdock.storage.repositories import AssignmentRepository, OrderRepository
from crossdock.text_pl import format_plan_label, plan_status_pl


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
    )
