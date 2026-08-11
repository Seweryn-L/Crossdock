"""Property-based invariants for routing solver (hypothesis)."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from crossdock.optimization.dto import RoutingRequest, VehicleRoutingInput
from crossdock.optimization.routing import solve_routes


def _sym_matrix(n: int, draw: st.DrawFn) -> tuple[tuple[int, ...], ...]:
    m = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = draw(st.integers(min_value=1_000, max_value=200_000))
            m[i][j] = d
            m[j][i] = d
    return tuple(tuple(row) for row in m)


@st.composite
def routing_instances(draw: st.DrawFn) -> RoutingRequest:
    n_drops = draw(st.integers(min_value=0, max_value=6))
    max_drops = draw(st.integers(min_value=1, max_value=3))
    matrix = _sym_matrix(n_drops + 1, draw)
    drop_keys = tuple(f"D{i}" for i in range(n_drops))
    order_ids_per_drop = tuple((100 + i,) for i in range(n_drops))
    weights = tuple(
        draw(st.floats(min_value=50, max_value=5000, allow_nan=False, allow_infinity=False))
        for _ in range(n_drops)
    )
    vehicle = VehicleRoutingInput(
        vehicle_id=1,
        vehicle_code="V1",
        drop_keys=drop_keys,
        order_ids_per_drop=order_ids_per_drop,
        drop_weights_kg=weights,
        distance_matrix_m=matrix,
    )
    return RoutingRequest(
        vehicles=(vehicle,),
        max_drops_per_route=max_drops,
        time_limit_s=2.0,
        seed=draw(st.integers(min_value=0, max_value=10_000)),
        cost_per_km=1.2,
    )


@given(routing_instances())
@settings(max_examples=30, deadline=None)
def test_routing_invariants(request: RoutingRequest) -> None:
    result = solve_routes(request)
    max_drops = request.max_drops_per_route
    input_ids: set[int] = set()
    for vehicle in request.vehicles:
        for group in vehicle.order_ids_per_drop:
            input_ids.update(group)

    routed: list[int] = []
    for route in result.routes:
        assert route.drop_count <= max_drops
        assert len(route.ordered_drop_keys) == route.drop_count
        assert len(set(route.ordered_order_ids)) == len(route.ordered_order_ids)
        # Sequences of order ids cover exactly the drops' orders without gaps in drop list
        assert route.drop_count == len(set(route.ordered_drop_keys))
        routed.extend(route.ordered_order_ids)

    assert len(routed) == len(set(routed))
    assert set(routed).isdisjoint(result.unrouted_order_ids)
    assert set(routed) | set(result.unrouted_order_ids) == input_ids
