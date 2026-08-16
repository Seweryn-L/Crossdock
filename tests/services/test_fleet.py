"""Fleet repository and Martyna seed tests."""

from __future__ import annotations

from sqlalchemy.orm import Session

from crossdock.domain.models import Vehicle, VehicleType
from crossdock.services.fleet import (
    seed_placeholder_fleet,
    sync_fleet_capacities_from_seed,
    sync_fleet_units,
)
from crossdock.storage.repositories import VehicleRepository


def test_seed_fleet_uses_martyna_capacities(db_session: Session) -> None:
    # 2 bus + 4 truck + 8 curtain
    assert seed_placeholder_fleet(db_session) == 14
    assert seed_placeholder_fleet(db_session) == 0
    vehicles = VehicleRepository(db_session).list_all()
    assert len(vehicles) == 14
    buses = [v for v in vehicles if v.vehicle_type == VehicleType.BUS]
    curtains = [v for v in vehicles if v.vehicle_type == VehicleType.CURTAIN]
    trucks = [v for v in vehicles if v.vehicle_type == VehicleType.TRUCK]
    assert len(buses) == 2
    assert all(v.pallet_capacity == 8 and v.weight_capacity_kg == 1050 for v in buses)
    assert all(v.pallet_capacity == 33 and v.weight_capacity_kg == 24500 for v in trucks)
    assert all(v.pallet_capacity == 33 and v.weight_capacity_kg == 24500 for v in curtains)
    assert all(not v.is_placeholder for v in vehicles)


def test_sync_updates_outdated_placeholder_capacities(db_session: Session) -> None:
    repo = VehicleRepository(db_session)
    repo.add(
        Vehicle(
            code="BUS-99",
            vehicle_type=VehicleType.BUS,
            pallet_capacity=10,
            weight_capacity_kg=3500,
            is_placeholder=True,
        )
    )
    assert sync_fleet_capacities_from_seed(db_session) == 1
    updated = next(v for v in repo.list_all() if v.code == "BUS-99")
    assert updated.pallet_capacity == 8
    assert updated.weight_capacity_kg == 1050
    assert updated.is_placeholder is False


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


def test_sync_fleet_units_grows_and_shrinks(db_session: Session) -> None:
    repo = VehicleRepository(db_session)
    seed_placeholder_fleet(db_session)
    grown = sync_fleet_units(
        db_session, vehicle_type=VehicleType.BUS, target_count=5, username="tester"
    )
    assert grown.created == 3
    assert len([v for v in repo.list_by_type(VehicleType.BUS) if v.is_active]) == 5

    shrunk = sync_fleet_units(
        db_session, vehicle_type=VehicleType.BUS, target_count=2, username="tester"
    )
    assert shrunk.deactivated == 3
    assert len([v for v in repo.list_by_type(VehicleType.BUS) if v.is_active]) == 2


def test_sync_fleet_units_skips_busy(db_session: Session) -> None:
    repo = VehicleRepository(db_session)
    a = repo.add(
        Vehicle(
            code="BUS-01",
            vehicle_type=VehicleType.BUS,
            pallet_capacity=8,
            weight_capacity_kg=1050,
        )
    )
    repo.add(
        Vehicle(
            code="BUS-02",
            vehicle_type=VehicleType.BUS,
            pallet_capacity=8,
            weight_capacity_kg=1050,
        )
    )
    repo.set_busy(a.id, busy=True)  # type: ignore[arg-type]
    result = sync_fleet_units(
        db_session, vehicle_type=VehicleType.BUS, target_count=0, username="tester"
    )
    assert result.deactivated == 1
    assert result.skipped_busy == 1
    still = repo.get_by_id(a.id)  # type: ignore[arg-type]
    assert still is not None and still.is_active and still.is_busy
