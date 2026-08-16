"""Fleet repository and placeholder seed tests."""

from __future__ import annotations

from sqlalchemy.orm import Session

from crossdock.domain.models import Vehicle, VehicleType
from crossdock.services.fleet import fleet_type_counts, seed_placeholder_fleet, sync_fleet_units
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


def test_list_available_excludes_busy(db_session: Session) -> None:
    repo = VehicleRepository(db_session)
    added = repo.add(
        Vehicle(
            code="T-1",
            vehicle_type=VehicleType.TRUCK,
            pallet_capacity=20,
            weight_capacity_kg=12000,
            is_placeholder=False,
        )
    )
    assert added.id is not None
    assert [v.code for v in repo.list_available()] == ["T-1"]
    repo.set_busy(added.id, True)
    assert repo.list_available() == []
    repo.set_busy(added.id, False)
    assert [v.code for v in repo.list_available()] == ["T-1"]


def test_sync_fleet_units_creates_and_deactivates(db_session: Session) -> None:
    assert seed_placeholder_fleet(db_session) == 14
    up = sync_fleet_units(
        db_session, vehicle_type=VehicleType.TRUCK, target_count=6, username="tester"
    )
    assert up.created == 2
    assert fleet_type_counts(db_session)["truck"]["active"] == 6
    down = sync_fleet_units(
        db_session, vehicle_type=VehicleType.TRUCK, target_count=3, username="tester"
    )
    assert down.deactivated == 3
    assert down.skipped_busy == 0
    assert fleet_type_counts(db_session)["truck"]["active"] == 3
