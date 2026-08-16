"""Warehouse occupancy snapshot for the Magazyn screen."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from crossdock.config import Settings, effective_planning_date, get_settings
from crossdock.domain.models import OrderStatus
from crossdock.domain.sla import must_leave_by, slack_days
from crossdock.services.plan_view import build_plan_view
from crossdock.storage.repositories import OrderRepository


@dataclass(frozen=True)
class WarehouseSnapshot:
    used_kg: float
    capacity_kg: float
    fill_ratio: float
    order_count: int
    nearest_must_leave: date | None
    nearest_slack: int | None
    overflow: bool
    planning_date: date


def warehouse_snapshot(
    session: Session,
    settings: Settings | None = None,
    *,
    run_id: int | None = None,
) -> WarehouseSnapshot:
    """Stock in the hub: NEW orders plus thin routes waiting to fill."""
    cfg = settings or get_settings()
    planning = effective_planning_date(cfg)
    lead = cfg.ship_lead_days
    capacity = float(cfg.warehouse_capacity_kg)
    orders_repo = OrderRepository(session)
    new_orders = list(orders_repo.list_by_status(OrderStatus.NEW))
    view = build_plan_view(session, settings=cfg, run_id=run_id)
    holding = []
    for oid in view.holding_order_ids:
        order = orders_repo.get_by_id(oid)
        if order is not None:
            holding.append(order)
    stock = new_orders + holding
    used = sum(float(o.total_weight_kg or 0.0) for o in stock)
    nearest_leave: date | None = None
    nearest_slack: int | None = None
    for order in stock:
        leave = must_leave_by(order.delivery_date, lead)
        slack = slack_days(order.delivery_date, planning, lead)
        if nearest_leave is None or leave < nearest_leave:
            nearest_leave = leave
            nearest_slack = slack
        elif nearest_leave == leave and (nearest_slack is None or slack < nearest_slack):
            nearest_slack = slack
    fill = (used / capacity) if capacity > 0 else 0.0
    return WarehouseSnapshot(
        used_kg=round(used, 1),
        capacity_kg=capacity,
        fill_ratio=fill,
        order_count=len(stock),
        nearest_must_leave=nearest_leave,
        nearest_slack=nearest_slack,
        overflow=bool(capacity > 0 and used > capacity),
        planning_date=planning,
    )
