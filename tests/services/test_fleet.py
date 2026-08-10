"""Fleet repository and placeholder seed tests."""

from __future__ import annotations

from sqlalchemy.orm import Session

from crossdock.domain.models import Vehicle, VehicleType
from crossdock.services.fleet import seed_placeholder_fleet
from crossdock.storage.repositories import VehicleRepository


def test_seed_placeholder_fleet_idempotent(db_session: Session) -> None:
    # 2 bus + 4 truck + 8 curtain
    assert seed_placeholder_fleet(db_session) == 14
    assert seed_placeholder_fleet(db_session) == 0
    vehicles = VehicleRepository(db_session).list_all()
    assert len(vehicles) == 14
    assert all(v.is_placeholder for v in vehicles)


def test_vehicle_update(db_session: Session) -> None:
    repo = VehicleRepository(db_session)
    added = repo.add(
        Vehicle(
            code="T-1",
            vehicle_type=VehicleType.BUS,
            pallet_capacity=5,
            weight_capacity_kg=2000,
            is_placeholder=True,
        )
    )
    updated = repo.update(added.model_copy(update={"pallet_capacity": 8, "is_placeholder": False}))
    assert updated is not None
    assert updated.pallet_capacity == 8
    assert updated.is_placeholder is False
