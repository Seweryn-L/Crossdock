"""Service-level tests for FR-022 buffering proposals."""

from __future__ import annotations

from datetime import date

from pydantic import SecretStr
from sqlalchemy.orm import Session

from crossdock.config import Settings
from crossdock.domain.models import Location, Order, OrderStatus, Shipment
from crossdock.services.buffering import (
    accept_buffer_proposals,
    list_buffer_candidates,
    propose_buffering,
)
from crossdock.services.warehouse_queue import list_queue
from crossdock.storage.repositories import OrderRepository


def _settings() -> Settings:
    return Settings(
        storage_secret=SecretStr("test-secret-not-for-production"),
        cost_per_km=1.2,
        storage_cost_per_pallet_day=2.0,
        ltl_cost_multiplier=1.8,
        buffer_savings_threshold=0.15,
        max_buffer_days=3,
        depot_latitude=51.176,
        depot_longitude=4.836,
    )


def test_propose_and_accept_buffer(db_session: Session) -> None:
    hub = Location(name="Hub", city="Antwerp", country="BE", latitude=51.22, longitude=4.40)
    dest = Location(name="Far", city="Paris", country="FR", latitude=48.85, longitude=2.35)
    saved = OrderRepository(db_session).add_many(
        [
            Order(
                delivery_code="BUF-SVC",
                shipments=[Shipment(shipment_number="S1", weight_kg=500, pallet_count=2)],
                pickup_location=hub,
                delivery_location=dest,
                delivery_date=date(2026, 8, 1),
                status=OrderStatus.NEW,
            )
        ]
    )[0]
    assert saved.id is not None

    bundle = propose_buffering(db_session, username="tester", settings=_settings())
    assert len(bundle.decisions) >= 1
    decision = next(d for d in bundle.decisions if d.order_id == saved.id)
    assert decision.action == "buffer"

    accepted = accept_buffer_proposals(
        db_session,
        order_ids=[saved.id],
        decisions_by_id={decision.order_id: decision},
        username="tester",
    )
    assert accepted == 1
    queue = list_queue(db_session)
    assert any(e.order_id == saved.id and e.status == "held" for e in queue)


def test_buffer_uses_default_kg_per_pallet_when_no_override(db_session: Session) -> None:
    hub = Location(name="Hub", city="Antwerp", country="BE", latitude=51.22, longitude=4.40)
    dest = Location(name="Far", city="Paris", country="FR", latitude=48.85, longitude=2.35)
    saved = OrderRepository(db_session).add_many(
        [
            Order(
                delivery_code="BUF-DEF",
                shipments=[Shipment(shipment_number="S2", weight_kg=1500)],
                pickup_location=hub,
                delivery_location=dest,
                delivery_date=date(2026, 8, 1),
                status=OrderStatus.NEW,
            )
        ]
    )[0]
    assert saved.id is not None
    settings = Settings(
        storage_secret=SecretStr("test-secret-not-for-production"),
        cost_per_km=1.2,
        storage_cost_per_pallet_day=2.0,
        ltl_cost_multiplier=1.8,
        buffer_savings_threshold=0.15,
        max_buffer_days=3,
        depot_latitude=51.176,
        depot_longitude=4.836,
        default_kg_per_pallet=500.0,
    )
    candidates = list_buffer_candidates(db_session, settings)
    match = next(c for c in candidates if c.order_id == saved.id)
    assert match.pallet_count == 3
