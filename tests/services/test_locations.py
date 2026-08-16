"""Tests for location coordinate seed and enrichment."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from crossdock.domain.models import Location, Order, OrderStatus, Shipment
from crossdock.excel_mapping import load_excel_column_mapping
from crossdock.services.import_orders import ImportOrdersService
from crossdock.services.locations import seed_location_coords
from crossdock.storage.repositories import LocationCoordsRepository, OrderRepository
from tests.fixtures.paths import e2open_order_fixtures

SEED_PATH = Path("config/location_coords_seed.json")
MAPPING = Path("config/excel_column_mapping.json")


def test_seed_location_coords_inserts_when_empty(db_session: Session) -> None:
    added = seed_location_coords(db_session, path=SEED_PATH)
    assert added >= 100
    assert LocationCoordsRepository(db_session).count() == added
    # Second call is idempotent when not empty.
    assert seed_location_coords(db_session, path=SEED_PATH) == 0


@pytest.mark.parametrize(
    "fixture",
    e2open_order_fixtures(),
    ids=lambda path: path.name,
)
def test_e2open_fixture_import_gets_coordinates(db_session: Session, fixture: Path) -> None:
    """Every pickup/delivery in the e2open fixtures must resolve from the seed."""
    mapping = load_excel_column_mapping(MAPPING)
    seed_location_coords(db_session, path=SEED_PATH)
    report = ImportOrdersService(db_session, mapping=mapping, default_delivery_days=7).import_path(
        fixture, username="tester"
    )
    assert report.accepted_count > 0
    orders = OrderRepository(db_session).list_all()
    missing = [
        o.delivery_code
        for o in orders
        if o.delivery_location.latitude is None
        or o.delivery_location.longitude is None
        or o.pickup_location.latitude is None
        or o.pickup_location.longitude is None
    ]
    assert missing == []


def test_enrich_existing_orders(db_session: Session) -> None:
    from crossdock.services.locations import apply_coords_to_existing_orders

    OrderRepository(db_session).add_many(
        [
            Order(
                delivery_code="X1",
                shipments=[Shipment(shipment_number="S1", weight_kg=100)],
                pickup_location=Location(name="Hub", city="ANTWERP", country="BE"),
                delivery_location=Location(
                    name="Cust", city="BLOIS", country="FR", postal_code="41000"
                ),
                delivery_date=date(2026, 6, 1),
                status=OrderStatus.NEW,
            )
        ]
    )
    LocationCoordsRepository(db_session).upsert(
        Location(
            name="Seed Blois",
            city="BLOIS",
            country="FR",
            postal_code="41000",
            latitude=47.59,
            longitude=1.33,
        )
    )
    updated = apply_coords_to_existing_orders(db_session)
    assert updated >= 1
    order = OrderRepository(db_session).list_all()[0]
    assert order.delivery_location.latitude == 47.59
