"""Tests for order delete repository methods."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from crossdock.domain.models import Location, Order, OrderStatus, Shipment
from crossdock.storage.repositories import OrderRepository


def _sample_order(code: str) -> Order:
    loc = Location(name="Hub", city="Antwerp", country="BE")
    dest = Location(name="Cust", city="Paris", country="FR")
    return Order(
        delivery_code=code,
        shipments=[Shipment(shipment_number=f"S-{code}", weight_kg=100.0)],
        pickup_location=loc,
        delivery_location=dest,
        delivery_date=date(2026, 8, 1),
        status=OrderStatus.NEW,
    )


def test_delete_by_ids(db_session: Session) -> None:
    repo = OrderRepository(db_session)
    saved = repo.add_many([_sample_order("A"), _sample_order("B")])
    assert repo.count() == 2
    oid = saved[0].id
    assert oid is not None
    assert repo.delete_by_ids([oid]) == 1
    assert repo.count() == 1


def test_delete_all(db_session: Session) -> None:
    repo = OrderRepository(db_session)
    repo.add_many([_sample_order("X"), _sample_order("Y")])
    assert repo.delete_all() == 2
    assert repo.count() == 0
