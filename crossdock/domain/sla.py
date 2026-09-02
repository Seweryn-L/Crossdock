"""Delivery-date SLA helpers for planning-day simulation.

Warehouse slack is measured against ``must_leave_by`` (last legal departure day).
That date comes from import (Pick Plan Date End) when available, otherwise from
``delivery_date - ship_lead_days`` as a fallback.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta


def must_leave_by_from_delivery(delivery_date: date, ship_lead_days: int) -> date:
    """Fallback when import has no Pick Plan Date End."""
    lead = max(int(ship_lead_days), 0)
    return delivery_date - timedelta(days=lead)


def resolve_must_leave_by(
    *,
    delivery_date: date,
    must_leave_by_imported: date | None,
    ship_lead_days: int,
) -> date:
    """Pick imported departure deadline or derive from delivery date."""
    if must_leave_by_imported is not None:
        return must_leave_by_imported
    return must_leave_by_from_delivery(delivery_date, ship_lead_days)


def slack_days(must_leave_by: date, planning_date: date) -> int:
    """Days of warehouse slack relative to planning day T.

    * ``< 0`` — already past last legal departure (overdue)
    * ``0`` — last legal departure day (must ship even if the truck is thin)
    * ``> 0`` — may wait for a fuller truck / same-drop companion
    """
    return (must_leave_by - planning_date).days


def slack_days_for_order(
    *,
    must_leave_by: date | None,
    delivery_date: date,
    planning_date: date,
    ship_lead_days: int,
) -> int:
    leave = resolve_must_leave_by(
        delivery_date=delivery_date,
        must_leave_by_imported=must_leave_by,
        ship_lead_days=ship_lead_days,
    )
    return slack_days(leave, planning_date)


def is_must_ship(slack: int) -> bool:
    return slack <= 0


def is_overdue(slack: int) -> bool:
    return slack < 0


def departure_is_legal(must_leave_by: date, planning_date: date) -> bool:
    """False when T is after the last legal departure day."""
    return planning_date <= must_leave_by


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


# Backward-compatible alias used in older tests/docs.
must_leave_by = must_leave_by_from_delivery
