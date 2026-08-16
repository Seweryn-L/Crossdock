"""Settings-aware pallet demand (cargo → vehicle type → default)."""

from __future__ import annotations

from crossdock.config import Settings, get_settings
from crossdock.domain.models import Order, Vehicle, VehicleType
from crossdock.domain.pallet_estimate import kg_per_pallet_for, resolve_pallet_demand


def _resolve_settings(settings: Settings | None) -> Settings | None:
    if settings is not None:
        return settings
    try:
        return get_settings()
    except Exception:
        return None


def type_kg_per_pallet(vehicle_type: VehicleType, settings: Settings | None = None) -> float:
    """Layer 2: runtime kg/pallet for a fleet type (Settings overlay, else seed)."""
    cfg = _resolve_settings(settings)
    if cfg is None:
        return kg_per_pallet_for(vehicle_type)
    overlay = {
        VehicleType.BUS: cfg.kg_per_pallet_bus,
        VehicleType.TRUCK: cfg.kg_per_pallet_truck,
        VehicleType.CURTAIN: cfg.kg_per_pallet_curtain,
    }
    return kg_per_pallet_for(vehicle_type, override=overlay[vehicle_type])


def cargo_table_pallets(order: Order) -> int | None:
    """Orders table: show a number only when the order has a cargo override."""
    weight = order.total_weight_kg or 0.0
    return resolve_pallet_demand(
        weight,
        explicit_pallets=order.total_pallets,
        cargo_kg_per_pallet=order.kg_per_pallet,
    )


def demand_on_vehicle(
    order: Order,
    vehicle: Vehicle,
    settings: Settings | None = None,
) -> int:
    """Plan/report: layer 1 if set, else layer 2 of this vehicle."""
    weight = order.total_weight_kg or 0.0
    demand = resolve_pallet_demand(
        weight,
        explicit_pallets=order.total_pallets,
        cargo_kg_per_pallet=order.kg_per_pallet,
        vehicle_kg_per_pallet=type_kg_per_pallet(vehicle.vehicle_type, settings),
    )
    return demand or 0


def demand_without_vehicle(order: Order, settings: Settings | None = None) -> int:
    """Buffer / queue: layer 1 if set, else default cargo denseness (layer 3)."""
    cfg = _resolve_settings(settings)
    default = cfg.default_kg_per_pallet if cfg is not None else kg_per_pallet_for(VehicleType.TRUCK)
    weight = order.total_weight_kg or 0.0
    demand = resolve_pallet_demand(
        weight,
        explicit_pallets=order.total_pallets,
        cargo_kg_per_pallet=order.kg_per_pallet,
        default_kg_per_pallet=default,
    )
    return demand or 0
