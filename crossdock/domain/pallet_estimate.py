"""Layered pallet demand: cargo override → vehicle type → default denseness."""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

from crossdock.domain.models import VehicleType

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "fleet_seed.json"

_DEFAULT_KG_PER_PALLET: dict[VehicleType, float] = {
    VehicleType.BUS: 1050.0 / 8.0,  # 131.25
    VehicleType.TRUCK: 24500.0 / 33.0,  # ≈742.424
    VehicleType.CURTAIN: 24500.0 / 33.0,
}


@lru_cache(maxsize=1)
def _load_kg_per_pallet() -> dict[VehicleType, float]:
    values = dict(_DEFAULT_KG_PER_PALLET)
    if not _CONFIG_PATH.is_file():
        return values
    data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    for item in data.get("vehicle_types", []):
        vtype = VehicleType(str(item["vehicle_type"]))
        if "kg_per_pallet" in item:
            values[vtype] = float(item["kg_per_pallet"])
        elif "pallet_capacity" in item and "weight_capacity_kg" in item:
            pallets = int(item["pallet_capacity"])
            if pallets > 0:
                values[vtype] = float(item["weight_capacity_kg"]) / pallets
    return values


def kg_per_pallet_for(vehicle_type: VehicleType, *, override: float | None = None) -> float:
    """Kilograms per europallet slot for a vehicle type (seed, unless overridden)."""
    if override is not None and override > 0:
        return float(override)
    return _load_kg_per_pallet()[vehicle_type]


def ceil_pallets(weight_kg: float, kg_per_pallet: float) -> int:
    """Ceil(weight / kg_per_pallet); at least 1 when weight > 0."""
    if weight_kg <= 0:
        return 0
    if kg_per_pallet <= 0:
        return 1
    return max(1, math.ceil(weight_kg / kg_per_pallet))


def resolve_pallet_demand(
    weight_kg: float,
    *,
    explicit_pallets: int | None = None,
    cargo_kg_per_pallet: float | None = None,
    vehicle_kg_per_pallet: float | None = None,
    default_kg_per_pallet: float | None = None,
) -> int | None:
    """Pallet demand: cargo override, else vehicle type, else default.

    Layer 1 — explicit pallets or cargo kg/pallet (vehicle-independent).
    Layer 2 — kg/pallet of the vehicle type being packed.
    Layer 3 — default cargo denseness when there is no vehicle context.
    Returns None when no denseness source is available.
    """
    if explicit_pallets is not None:
        return max(0, int(explicit_pallets))
    if cargo_kg_per_pallet is not None and cargo_kg_per_pallet > 0:
        return ceil_pallets(weight_kg, cargo_kg_per_pallet)
    if vehicle_kg_per_pallet is not None and vehicle_kg_per_pallet > 0:
        return ceil_pallets(weight_kg, vehicle_kg_per_pallet)
    if default_kg_per_pallet is not None and default_kg_per_pallet > 0:
        return ceil_pallets(weight_kg, default_kg_per_pallet)
    return None


def estimate_pallets(
    weight_kg: float,
    vehicle_type: VehicleType,
    *,
    kg_per_pallet: float | None = None,
) -> int:
    """Layer-2 estimate for a vehicle type (no cargo override)."""
    denseness = kg_per_pallet_for(vehicle_type, override=kg_per_pallet)
    return resolve_pallet_demand(weight_kg, vehicle_kg_per_pallet=denseness) or 0


def clear_kg_per_pallet_cache() -> None:
    """Test helper — reload config after mutating fleet_seed.json."""
    _load_kg_per_pallet.cache_clear()
