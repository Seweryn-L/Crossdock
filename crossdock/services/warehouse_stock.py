"""Warehouse occupancy snapshot for the Magazyn screen."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from crossdock.config import Settings, effective_planning_date, get_settings
from crossdock.domain.models import Order, OrderStatus
from crossdock.domain.sla import resolve_must_leave_by, slack_days_for_order
from crossdock.storage.repositories import AssignmentRepository, OrderRepository

_WAREHOUSE_ORDER_STATUSES = frozenset({OrderStatus.NEW, OrderStatus.PLANNED, OrderStatus.APPROVED})
_DEPARTED_ROUTE_STATUSES = frozenset({"in_transit", "completed"})


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


def _resolve_run_id(repo: AssignmentRepository, run_id: int | None) -> int | None:
    if run_id is not None:
        return run_id if repo.get_run(run_id) is not None else None
    latest = repo.get_latest_run()
    return latest.id if latest is not None else None


def _order_ids_on_departed_routes(session: Session, run_id: int | None) -> set[int]:
    """Order IDs assigned to in-transit or completed routes of the active plan."""
    repo = AssignmentRepository(session)
    resolved = _resolve_run_id(repo, run_id)
    if resolved is None:
        return set()
    departed_vehicles = {
        route.vehicle_code
        for route in repo.list_routes_for_run(resolved)
        if route.route_status in _DEPARTED_ROUTE_STATUSES
    }
    if not departed_vehicles:
        return set()
    return {
        item.order_id
        for item in repo.list_items_for_run(resolved)
        if item.vehicle_code in departed_vehicles
    }


def _warehouse_stock_orders(
    session: Session,
    *,
    run_id: int | None = None,
) -> list[Order]:
    """Orders physically in the hub (NEW/PLANNED/APPROVED, not on departed routes)."""
    orders_repo = OrderRepository(session)
    stock_by_id: dict[int, Order] = {}
    for status in _WAREHOUSE_ORDER_STATUSES:
        for order in orders_repo.list_by_status(status):
            if order.id is not None:
                stock_by_id[order.id] = order
    for oid in _order_ids_on_departed_routes(session, run_id):
        stock_by_id.pop(oid, None)
    return list(stock_by_id.values())


def warehouse_snapshot(
    session: Session,
    settings: Settings | None = None,
    *,
    run_id: int | None = None,
) -> WarehouseSnapshot:
    """Stock in the hub: open orders not yet on departed routes."""
    cfg = settings or get_settings()
    planning = effective_planning_date(cfg)
    lead = cfg.ship_lead_days
    capacity = float(cfg.warehouse_capacity_kg)
    stock = _warehouse_stock_orders(session, run_id=run_id)
    used = sum(float(o.total_weight_kg or 0.0) for o in stock)
    nearest_leave: date | None = None
    nearest_slack: int | None = None
    for order in stock:
        leave = resolve_must_leave_by(
            delivery_date=order.delivery_date,
            must_leave_by_imported=order.must_leave_by,
            ship_lead_days=lead,
        )
        slack = slack_days_for_order(
            must_leave_by=order.must_leave_by,
            delivery_date=order.delivery_date,
            planning_date=planning,
            ship_lead_days=lead,
        )
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
