"""Per-vehicle cost_per_km override for route cost_eur."""

from __future__ import annotations

from crossdock.optimization.dto import RoutingRequest, VehicleRoutingInput
from crossdock.optimization.routing import solve_routes


def _matrix_two_drops() -> tuple[tuple[int, ...], ...]:
    # depot + 1 drop: 100 km = 100_000 m each way
    return (
        (0, 100_000),
        (100_000, 0),
    )


def test_different_vehicle_rates_yield_different_costs() -> None:
    matrix = _matrix_two_drops()
    slow = VehicleRoutingInput(
        vehicle_id=1,
        vehicle_code="A",
        drop_keys=("D1",),
        order_ids_per_drop=((10,),),
        drop_weights_kg=(1000.0,),
        distance_matrix_m=matrix,
        cost_per_km=1.0,
    )
    fast = VehicleRoutingInput(
        vehicle_id=2,
        vehicle_code="B",
        drop_keys=("D2",),
        order_ids_per_drop=((20,),),
        drop_weights_kg=(1000.0,),
        distance_matrix_m=matrix,
        cost_per_km=2.0,
    )
    result = solve_routes(
        RoutingRequest(
            vehicles=(slow, fast),
            max_drops_per_route=3,
            time_limit_s=2.0,
            seed=1,
            cost_per_km=1.2,
        )
    )
    by_code = {r.vehicle_code: r for r in result.routes}
    assert by_code["A"].distance_km == by_code["B"].distance_km
    assert by_code["A"].cost_eur == by_code["A"].distance_km * 1.0
    assert by_code["B"].cost_eur == by_code["B"].distance_km * 2.0
    assert by_code["A"].cost_eur != by_code["B"].cost_eur
