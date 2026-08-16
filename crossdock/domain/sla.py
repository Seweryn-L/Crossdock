"""Delivery-date SLA helpers for planning-day simulation.

Transit MVP: an order with delivery date D must leave the warehouse by
``D - ship_lead_days`` (default 2). Shipping on the delivery day is not
allowed. Slack is measured against that last legal departure day.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta


def must_leave_by(delivery_date: date, ship_lead_days: int) -> date:
    """Last calendar day the order may still leave the warehouse."""
    lead = max(int(ship_lead_days), 0)
    return delivery_date - timedelta(days=lead)


def slack_days(delivery_date: date, planning_date: date, ship_lead_days: int) -> int:
    """Days of warehouse slack relative to planning day T.

    * ``< 0`` — already past last legal departure (overdue)
    * ``0`` — last legal departure day (must ship even if the truck is thin)
    * ``> 0`` — may wait for a fuller truck / same-drop companion
    """
    return (must_leave_by(delivery_date, ship_lead_days) - planning_date).days


def is_must_ship(slack: int) -> bool:
    return slack <= 0


def is_overdue(slack: int) -> bool:
    return slack < 0


def departure_is_legal(delivery_date: date, planning_date: date, ship_lead_days: int) -> bool:
    """False when T is on/after the delivery date (same-day delivery forbidden)."""
    return planning_date <= must_leave_by(delivery_date, ship_lead_days)


def route_should_send(
    *,
    fill_ratio: float | None,
    min_fill_ratio: float,
    slacks: Sequence[int],
) -> bool:
    """Whether a packed route should leave today.

    Send when any order has no slack left, or the truck meets the fill
    threshold. Thin trucks with remaining SLA wait for more freight.
    """
    if any(is_must_ship(s) for s in slacks):
        return True
    if fill_ratio is None:
        return True
    return fill_ratio + 1e-9 >= float(min_fill_ratio)
