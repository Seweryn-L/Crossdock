"""PlanningService integration tests."""

from __future__ import annotations

from datetime import date

from pydantic import SecretStr
from sqlalchemy.orm import Session

from crossdock.config import Settings
from crossdock.domain.models import Location, Order, OrderStatus, Shipment, Vehicle, VehicleType
from crossdock.services.planning import PlanningService
from crossdock.storage.repositories import OrderRepository, VehicleRepository


def _settings() -> Settings:
    return Settings(
        storage_secret=SecretStr("test-secret-not-for-production"),
        solver_time_limit_s=5.0,
        solver_seed=42,
    )


def test_planning_service_assigns_and_persists(db_session: Session) -> None:
    orders = OrderRepository(db_session)
    vehicles = VehicleRepository(db_session)
    vehicles.add(
        Vehicle(
            code="T1",
            vehicle_type=VehicleType.TRUCK,
            pallet_capacity=20,
            weight_capacity_kg=12000,
            is_placeholder=False,
        )
    )
    loc = Location(name="Hub", city="Antwerp", country="BE")
    dest = Location(name="Cust", city="Paris", country="FR")
    for i, w in enumerate([2000.0, 3000.0, 4000.0], start=1):
        orders.add_many(
            [
                Order(
                    delivery_code=f"ORD-{i}",
                    shipments=[Shipment(shipment_number=f"S-{i}", weight_kg=w)],
                    pickup_location=loc,
                    delivery_location=dest,
                    delivery_date=date(2026, 8, 1),
                    status=OrderStatus.NEW,
                )
            ]
        )

    outcome = PlanningService(db_session, settings=_settings()).run_assignment(username="tester")
    assert outcome.run_id >= 1
    assert outcome.result.status in {"OPTIMAL", "FEASIBLE"}
    assert len(outcome.result.assigned_order_ids) == 3
