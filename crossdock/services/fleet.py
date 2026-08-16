"""Fleet seed — PLACEHOLDER capacities until Martyna's table (W-03).

Multiple units so a full e2open sample (~50 orders) can get partial
assignment; capacities remain placeholders.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TypedDict

from sqlalchemy.orm import Session

from crossdock.domain.models import Vehicle, VehicleType
from crossdock.storage.repositories import AuditLogRepository, VehicleRepository


class FleetTypeSpec(TypedDict):
    vehicle_type: str
    pallet_capacity: int
    weight_capacity_kg: float
    kg_per_pallet: int


_FLEET_TYPE_SPECS: tuple[FleetTypeSpec, ...] = (
    {
        "vehicle_type": "bus",
        "pallet_capacity": 10,
        "weight_capacity_kg": 3500.0,
        "kg_per_pallet": 350,
    },
    {
        "vehicle_type": "truck",
        "pallet_capacity": 20,
        "weight_capacity_kg": 12000.0,
        "kg_per_pallet": 600,
    },
    {
        "vehicle_type": "curtain",
        "pallet_capacity": 33,
        "weight_capacity_kg": 24000.0,
        "kg_per_pallet": 727,
    },
)

_TYPE_PREFIX: dict[VehicleType, str] = {
    VehicleType.BUS: "BUS",
    VehicleType.TRUCK: "TRUCK",
    VehicleType.CURTAIN: "CURTAIN",
}


def fleet_type_specs() -> list[FleetTypeSpec]:
    return [spec.copy() for spec in _FLEET_TYPE_SPECS]


def spec_for_type(vehicle_type: VehicleType) -> FleetTypeSpec:
    for spec in _FLEET_TYPE_SPECS:
        if spec["vehicle_type"] == vehicle_type.value:
            return spec.copy()
    raise ValueError(f"Nieznany typ pojazdu: {vehicle_type.value}")


def fleet_type_counts(session: Session) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {
        spec["vehicle_type"]: {"active": 0, "busy": 0, "total": 0} for spec in _FLEET_TYPE_SPECS
    }
    for vehicle in VehicleRepository(session).list_all():
        bucket = counts.setdefault(vehicle.vehicle_type.value, {"active": 0, "busy": 0, "total": 0})
        bucket["total"] += 1
        if vehicle.is_active:
            bucket["active"] += 1
        if vehicle.is_busy:
            bucket["busy"] += 1
    return counts


@dataclass(frozen=True)
class SyncFleetResult:
    created: int
    activated: int
    deactivated: int
    skipped_busy: int


def _next_code(existing: list[Vehicle], prefix: str) -> str:
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$", re.IGNORECASE)
    used = 0
    for vehicle in existing:
        match = pattern.match(vehicle.code)
        if match:
            used = max(used, int(match.group(1)))
    return f"{prefix}-{used + 1:02d}"


def sync_fleet_units(
    session: Session,
    *,
    vehicle_type: VehicleType,
    target_count: int,
    username: str,
) -> SyncFleetResult:
    if target_count < 0:
        raise ValueError("Liczba pojazdów nie może być ujemna.")
    repo = VehicleRepository(session)
    of_type = repo.list_by_type(vehicle_type)
    active = [v for v in of_type if v.is_active]
    inactive = [v for v in of_type if not v.is_active]
    spec = spec_for_type(vehicle_type)
    created = 0
    activated = 0
    deactivated = 0
    skipped_busy = 0

    while len(active) < target_count and inactive:
        vehicle = inactive.pop(0)
        if vehicle.id is None:
            continue
        repo.update(vehicle.model_copy(update={"is_active": True}))
        activated += 1
        active.append(vehicle)

    while len(active) < target_count:
        code = _next_code(repo.list_by_type(vehicle_type), _TYPE_PREFIX[vehicle_type])
        added = repo.add(
            Vehicle(
                code=code,
                vehicle_type=vehicle_type,
                pallet_capacity=spec["pallet_capacity"],
                weight_capacity_kg=spec["weight_capacity_kg"],
                is_active=True,
                is_placeholder=True,
            )
        )
        created += 1
        active.append(added)

    extras = sorted(
        (v for v in active if v.id is not None),
        key=lambda v: v.code,
        reverse=True,
    )
    for vehicle in extras:
        if len(active) <= target_count:
            break
        if vehicle.is_busy:
            skipped_busy += 1
            continue
        assert vehicle.id is not None
        repo.update(vehicle.model_copy(update={"is_active": False}))
        deactivated += 1
        active = [v for v in active if v.id != vehicle.id]
    AuditLogRepository(session).record(
        username=username,
        action="fleet.sync_units",
        details={
            "vehicle_type": vehicle_type.value,
            "target_count": target_count,
            "created": created,
            "activated": activated,
            "deactivated": deactivated,
            "skipped_busy": skipped_busy,
        },
    )
    return SyncFleetResult(
        created=created,
        activated=activated,
        deactivated=deactivated,
        skipped_busy=skipped_busy,
    )


def _placeholder_fleet() -> list[Vehicle]:
    fleet: list[Vehicle] = []
    for i in range(1, 3):
        fleet.append(
            Vehicle(
                code=f"BUS-{i:02d}",
                vehicle_type=VehicleType.BUS,
                pallet_capacity=10,
                weight_capacity_kg=3500,
                is_placeholder=True,
            )
        )
    for i in range(1, 5):
        fleet.append(
            Vehicle(
                code=f"TRUCK-{i:02d}",
                vehicle_type=VehicleType.TRUCK,
                pallet_capacity=20,
                weight_capacity_kg=12000,
                is_placeholder=True,
            )
        )
    for i in range(1, 9):
        fleet.append(
            Vehicle(
                code=f"CURTAIN-{i:02d}",
                vehicle_type=VehicleType.CURTAIN,
                pallet_capacity=33,
                weight_capacity_kg=24000,
                is_placeholder=True,
            )
        )
    return fleet


def seed_placeholder_fleet(session: Session) -> int:
    """Insert placeholder vehicles when the fleet table is empty. Returns count added."""
    repo = VehicleRepository(session)
    if repo.count() > 0:
        return 0
    fleet = _placeholder_fleet()
    for vehicle in fleet:
        repo.add(vehicle)
    AuditLogRepository(session).record(
        username="system",
        action="fleet.seed_placeholder",
        details={
            "count": len(fleet),
            "note": "PLACEHOLDER_PENDING_MARTYNA — docs/otwarte_wejscia_zespolu.md W-03",
        },
    )
    return len(fleet)
