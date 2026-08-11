"""Dashboard KPI aggregator for the home page."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from crossdock.domain.models import OrderStatus
from crossdock.services.plan_view import build_plan_view
from crossdock.services.system_status import collect_system_status
from crossdock.services.warehouse_queue import list_queue
from crossdock.storage.repositories import OrderRepository
from crossdock.text_pl import plan_status_pl


@dataclass(frozen=True)
class DashboardSnapshot:
    total_orders: int
    new_orders: int
    planned_orders: int
    approved_orders: int
    latest_plan_id: int | None
    latest_plan_status_pl: str | None
    riding: int
    staying: int
    attention: int
    queue_count: int
    last_import_summary: str | None
    staying_order_ids: tuple[int, ...]


def collect_dashboard(session: Session) -> DashboardSnapshot:
    orders = OrderRepository(session)
    total = orders.count()
    new_n = len(orders.list_by_status(OrderStatus.NEW))
    planned_n = len(orders.list_by_status(OrderStatus.PLANNED))
    approved_n = len(orders.list_by_status(OrderStatus.APPROVED))
    view = build_plan_view(session)
    status = collect_system_status(session)
    queue_count = len(list_queue(session))

    plan_id = view.summary.run_id if view.summary else None
    plan_status = plan_status_pl(view.summary.plan_status) if view.summary else None
    return DashboardSnapshot(
        total_orders=total,
        new_orders=new_n,
        planned_orders=planned_n,
        approved_orders=approved_n,
        latest_plan_id=plan_id,
        latest_plan_status_pl=plan_status,
        riding=view.summary.riding if view.summary else 0,
        staying=view.summary.staying if view.summary else 0,
        attention=view.summary.attention if view.summary else 0,
        queue_count=queue_count,
        last_import_summary=status.last_import_summary,
        staying_order_ids=view.staying_order_ids if view.summary else (),
    )
