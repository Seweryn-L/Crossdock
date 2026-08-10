"""Fleet seed — PLACEHOLDER capacities until Martyna's table (W-03).

Multiple units so a full e2open sample (~50 orders) can get partial
assignment; capacities remain placeholders.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from crossdock.domain.models import Vehicle, VehicleType
from crossdock.storage.repositories import AuditLogRepository, VehicleRepository


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
