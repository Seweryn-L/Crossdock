"""Fleet seed — capacities from config/fleet_seed.json.

Unit counts are set in UI (seed 2/4/8 is a start, not a target).
Capacities (pallets / kg) come from the fleet table.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from crossdock.domain.models import Vehicle, VehicleType
from crossdock.storage.repositories import AuditLogRepository, VehicleRepository

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "fleet_seed.json"

# Fallback if config/fleet_seed.json is missing (same values as Drive FLota).
_DEFAULT_CAPACITIES: dict[VehicleType, tuple[int, float]] = {
    VehicleType.BUS: (8, 1050.0),
    VehicleType.TRUCK: (33, 24500.0),
    VehicleType.CURTAIN: (33, 24500.0),
}
_DEFAULT_UNITS: dict[VehicleType, int] = {
    VehicleType.BUS: 2,
    VehicleType.TRUCK: 4,
    VehicleType.CURTAIN: 8,
}


def _load_seed_spec() -> tuple[dict[VehicleType, tuple[int, float]], dict[VehicleType, int]]:
    capacities = dict(_DEFAULT_CAPACITIES)
    units = dict(_DEFAULT_UNITS)
    if not _CONFIG_PATH.is_file():
        return capacities, units
    data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    for item in data.get("vehicle_types", []):
        vtype = VehicleType(str(item["vehicle_type"]))
        capacities[vtype] = (int(item["pallet_capacity"]), float(item["weight_capacity_kg"]))
    seed_units = data.get("seed_units") or {}
    for key, count in seed_units.items():
        units[VehicleType(str(key))] = int(count)
    return capacities, units


def fleet_type_specs() -> list[dict[str, object]]:
    """UI-facing rows: capacity from seed + editable kg/pallet (runtime overlay)."""
    from crossdock.services.pallet_demand import type_kg_per_pallet

    capacities, _ = _load_seed_spec()
    rows: list[dict[str, object]] = []
    for vtype in (VehicleType.BUS, VehicleType.TRUCK, VehicleType.CURTAIN):
        pallets, weight = capacities[vtype]
        rows.append(
            {
                "vehicle_type": vtype.value,
                "pallet_capacity": pallets,
                "weight_capacity_kg": weight,
                "kg_per_pallet": round(type_kg_per_pallet(vtype), 3),
            }
        )
    return rows


def fleet_type_counts(session: Session) -> dict[str, dict[str, int]]:
    """Active / busy / total unit counts per vehicle type."""
    repo = VehicleRepository(session)
    out: dict[str, dict[str, int]] = {}
    for vtype in (VehicleType.BUS, VehicleType.TRUCK, VehicleType.CURTAIN):
        units = repo.list_by_type(vtype)
        active = [u for u in units if u.is_active]
        busy = [u for u in active if u.is_busy]
        out[vtype.value] = {
            "active": len(active),
            "busy": len(busy),
            "total": len(units),
        }
    return out


@dataclass(frozen=True, slots=True)
class SyncFleetResult:
    vehicle_type: str
    target_count: int
    activated: int
    created: int
    deactivated: int
    skipped_busy: int


def sync_fleet_units(
    session: Session,
    *,
    vehicle_type: VehicleType,
    target_count: int,
    username: str,
) -> SyncFleetResult:
    """Set active unit count for a type: create/reactivate up, deactivate excess.

    Busy approved vehicles are never deactivated (counted in skipped_busy).
    Codes use PREFIX-01…N. Does not delete rows (history-safe).
    """
    if target_count < 0:
        raise ValueError("target_count must be >= 0")

    capacities, _ = _load_seed_spec()
    pallets, weight = capacities[vehicle_type]
    prefixes = {
        VehicleType.BUS: "BUS",
        VehicleType.TRUCK: "TRUCK",
        VehicleType.CURTAIN: "CURTAIN",
    }
    prefix = prefixes[vehicle_type]
    repo = VehicleRepository(session)
    existing = sorted(repo.list_by_type(vehicle_type), key=lambda v: v.code)

    activated = created = deactivated = skipped_busy = 0
    active = [v for v in existing if v.is_active]
    inactive = [v for v in existing if not v.is_active]

    def _next_code() -> str:
        used = {v.code for v in existing}
        n = 1
        while True:
            candidate = f"{prefix}-{n:02d}"
            if candidate not in used:
                return candidate
            n += 1

    # Grow: reactivate inactive first, then create new codes.
    while len(active) < target_count:
        if inactive:
            vehicle = inactive.pop(0)
            updated = repo.update(
                vehicle.model_copy(
                    update={
                        "is_active": True,
                        "pallet_capacity": pallets,
                        "weight_capacity_kg": weight,
                        "is_placeholder": False,
                    }
                )
            )
            assert updated is not None
            active.append(updated)
            activated += 1
            continue
        saved = repo.add(
            Vehicle(
                code=_next_code(),
                vehicle_type=vehicle_type,
                pallet_capacity=pallets,
                weight_capacity_kg=weight,
                is_active=True,
                is_placeholder=False,
            )
        )
        existing.append(saved)
        active.append(saved)
        created += 1

    # Shrink: deactivate non-busy active units beyond target (highest code first).
    if len(active) > target_count:
        shrinkable = sorted(
            [v for v in active if not v.is_busy],
            key=lambda v: v.code,
            reverse=True,
        )
        need_remove = len(active) - target_count
        if len(shrinkable) < need_remove:
            skipped_busy = need_remove - len(shrinkable)
            need_remove = len(shrinkable)
        for vehicle in shrinkable[:need_remove]:
            repo.update(vehicle.model_copy(update={"is_active": False}))
            deactivated += 1

    AuditLogRepository(session).record(
        username=username,
        action="fleet.sync_units",
        details={
            "vehicle_type": vehicle_type.value,
            "target_count": target_count,
            "activated": activated,
            "created": created,
            "deactivated": deactivated,
            "skipped_busy": skipped_busy,
        },
    )
    return SyncFleetResult(
        vehicle_type=vehicle_type.value,
        target_count=target_count,
        activated=activated,
        created=created,
        deactivated=deactivated,
        skipped_busy=skipped_busy,
    )

def _martyna_fleet() -> list[Vehicle]:
    capacities, units = _load_seed_spec()
    fleet: list[Vehicle] = []
    prefixes = {
        VehicleType.BUS: "BUS",
        VehicleType.TRUCK: "TRUCK",
        VehicleType.CURTAIN: "CURTAIN",
    }
    for vtype, count in units.items():
        pallets, weight = capacities[vtype]
        prefix = prefixes[vtype]
        for i in range(1, count + 1):
            fleet.append(
                Vehicle(
                    code=f"{prefix}-{i:02d}",
                    vehicle_type=vtype,
                    pallet_capacity=pallets,
                    weight_capacity_kg=weight,
                    is_placeholder=False,
                )
            )
    return fleet


def seed_placeholder_fleet(session: Session) -> int:
    """Insert fleet seed when the vehicles table is empty. Returns count added.

    Name kept for call-site compatibility; capacities are no longer placeholders.
    """
    repo = VehicleRepository(session)
    if repo.count() > 0:
        return 0
    fleet = _martyna_fleet()
    for vehicle in fleet:
        repo.add(vehicle)
    AuditLogRepository(session).record(
        username="system",
        action="fleet.seed",
        details={
            "count": len(fleet),
            "note": "capacities from config/fleet_seed.json",
        },
    )
    return len(fleet)


def sync_fleet_capacities_from_seed(session: Session) -> int:
    """Update active seeded vehicles to Martyna capacities when still outdated.

    Safe for DBs created before W-03 arrival (old placeholder kg/pallets).
    Matches by code prefix BUS-/TRUCK-/CURTAIN-. Returns number of rows updated.
    """
    capacities, _ = _load_seed_spec()
    repo = VehicleRepository(session)
    updated = 0
    for vehicle in repo.list_all():
        prefix = vehicle.code.split("-", 1)[0].upper()
        if prefix not in {"BUS", "TRUCK", "CURTAIN"}:
            continue
        vtype = vehicle.vehicle_type
        if vtype not in capacities:
            continue
        pallets, weight = capacities[vtype]
        if (
            vehicle.pallet_capacity == pallets
            and vehicle.weight_capacity_kg == weight
            and not vehicle.is_placeholder
        ):
            continue
        repo.update(
            vehicle.model_copy(
                update={
                    "pallet_capacity": pallets,
                    "weight_capacity_kg": weight,
                    "is_placeholder": False,
                }
            )
        )
        updated += 1
    if updated:
        AuditLogRepository(session).record(
            username="system",
            action="fleet.sync_capacities",
            details={"updated": updated, "source": "config/fleet_seed.json"},
        )
    return updated
