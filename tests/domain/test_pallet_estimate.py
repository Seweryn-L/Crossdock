"""Tests for layered pallet demand (cargo / vehicle type / default)."""

from __future__ import annotations

from hypothesis import assume, given
from hypothesis import strategies as st

from crossdock.domain.models import VehicleType
from crossdock.domain.pallet_estimate import (
    ceil_pallets,
    estimate_pallets,
    kg_per_pallet_for,
    resolve_pallet_demand,
)


def test_kg_per_pallet_bus_and_ftl() -> None:
    assert abs(kg_per_pallet_for(VehicleType.BUS) - 131.25) < 1e-6
    assert abs(kg_per_pallet_for(VehicleType.TRUCK) - (24500.0 / 33.0)) < 1e-6
    assert abs(kg_per_pallet_for(VehicleType.CURTAIN) - (24500.0 / 33.0)) < 1e-6


def test_estimate_pallets_ceil() -> None:
    assert estimate_pallets(0, VehicleType.BUS) == 0
    assert estimate_pallets(131.25, VehicleType.BUS) == 1
    assert estimate_pallets(131.26, VehicleType.BUS) == 2
    assert estimate_pallets(2000, VehicleType.BUS) == 16
    assert estimate_pallets(2000, VehicleType.CURTAIN) == 3


def test_same_kg_two_types_differ_without_cargo_override() -> None:
    """Same weight on bus vs curtain yields different pallet demand."""
    weight = 2000.0
    bus = resolve_pallet_demand(weight, vehicle_kg_per_pallet=kg_per_pallet_for(VehicleType.BUS))
    curtain = resolve_pallet_demand(
        weight, vehicle_kg_per_pallet=kg_per_pallet_for(VehicleType.CURTAIN)
    )
    assert bus == 16
    assert curtain == 3
    assert bus != curtain


def test_cargo_override_is_vehicle_independent() -> None:
    weight = 2000.0
    bus = resolve_pallet_demand(
        weight,
        cargo_kg_per_pallet=500.0,
        vehicle_kg_per_pallet=kg_per_pallet_for(VehicleType.BUS),
    )
    curtain = resolve_pallet_demand(
        weight,
        cargo_kg_per_pallet=500.0,
        vehicle_kg_per_pallet=kg_per_pallet_for(VehicleType.CURTAIN),
    )
    assert bus == curtain == 4


def test_explicit_pallets_win_over_cargo_and_vehicle() -> None:
    assert (
        resolve_pallet_demand(
            2000.0,
            explicit_pallets=7,
            cargo_kg_per_pallet=500.0,
            vehicle_kg_per_pallet=131.25,
        )
        == 7
    )


def test_orders_table_blank_without_override() -> None:
    assert (
        resolve_pallet_demand(
            2000.0,
            vehicle_kg_per_pallet=None,
            default_kg_per_pallet=None,
        )
        is None
    )


def test_layer3_default_when_no_vehicle() -> None:
    assert resolve_pallet_demand(1500.0, default_kg_per_pallet=500.0) == 3


def test_override_param_wins_over_seed() -> None:
    assert kg_per_pallet_for(VehicleType.BUS, override=200.0) == 200.0


@given(
    weight=st.floats(min_value=100.0, max_value=20000.0, allow_nan=False, allow_infinity=False),
    kpp_a=st.floats(min_value=80.0, max_value=200.0, allow_nan=False, allow_infinity=False),
    kpp_b=st.floats(min_value=500.0, max_value=900.0, allow_nan=False, allow_infinity=False),
)
def test_same_kg_two_types_demand_may_differ(weight: float, kpp_a: float, kpp_b: float) -> None:
    demand_a = resolve_pallet_demand(weight, vehicle_kg_per_pallet=kpp_a)
    demand_b = resolve_pallet_demand(weight, vehicle_kg_per_pallet=kpp_b)
    assert demand_a == ceil_pallets(weight, kpp_a)
    assert demand_b == ceil_pallets(weight, kpp_b)
    assume(weight > max(kpp_a, kpp_b) * 2)
    assert demand_a != demand_b


@given(
    weight=st.floats(min_value=100.0, max_value=20000.0, allow_nan=False, allow_infinity=False),
    cargo=st.floats(min_value=100.0, max_value=800.0, allow_nan=False, allow_infinity=False),
    kpp_a=st.floats(min_value=80.0, max_value=200.0, allow_nan=False, allow_infinity=False),
    kpp_b=st.floats(min_value=500.0, max_value=900.0, allow_nan=False, allow_infinity=False),
)
def test_cargo_override_equalizes_types(
    weight: float, cargo: float, kpp_a: float, kpp_b: float
) -> None:
    a = resolve_pallet_demand(weight, cargo_kg_per_pallet=cargo, vehicle_kg_per_pallet=kpp_a)
    b = resolve_pallet_demand(weight, cargo_kg_per_pallet=cargo, vehicle_kg_per_pallet=kpp_b)
    assert a == b == ceil_pallets(weight, cargo)
