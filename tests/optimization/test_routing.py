"""Golden tests for drop routing and trim logic."""

from __future__ import annotations

from crossdock.optimization.dto import RoutingRequest, VehicleRoutingInput
from crossdock.optimization.routing import solve_routes, trim_drops


def _matrix_for_points_km(points: list[tuple[float, float]]) -> tuple[tuple[int, ...], ...]:
    """Build metre matrix from (lat, lon) via crude equirectangular for tests."""
    # Use simple degree delta * 111 km for deterministic tests (not haversine).
    n = len(points)
    m = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            dlat = points[i][0] - points[j][0]
            dlon = points[i][1] - points[j][1]
            km = ((dlat * 111) ** 2 + (dlon * 111) ** 2) ** 0.5
            m[i][j] = round(km * 1000)
    return tuple(tuple(row) for row in m)


def test_three_drops_produce_sequence_and_distance() -> None:
    # depot + 3 drops
    points = [(51.18, 4.84), (51.20, 4.90), (51.10, 4.80), (51.30, 5.00)]
    matrix = _matrix_for_points_km(points)
    vehicle = VehicleRoutingInput(
        vehicle_id=1,
        vehicle_code="T1",
        drop_keys=("A", "B", "C"),
        order_ids_per_drop=((10,), (20,), (30,)),
        drop_weights_kg=(1000.0, 2000.0, 1500.0),
        distance_matrix_m=matrix,
    )
    result = solve_routes(
        RoutingRequest(vehicles=(vehicle,), max_drops_per_route=3, time_limit_s=2.0, seed=1)
    )
    assert result.status in {"OPTIMAL", "FEASIBLE", "FALLBACK"}
    assert len(result.routes) == 1
    route = result.routes[0]
    assert route.drop_count == 3
    assert set(route.ordered_order_ids) == {10, 20, 30}
    assert len(route.ordered_drop_keys) == 3
    assert route.distance_km > 0
    assert result.unrouted_order_ids == ()


def test_four_drops_trimmed_to_max_three() -> None:
    points = [
        (51.18, 4.84),  # depot
        (51.19, 4.85),  # closest
        (51.20, 4.86),
        (51.21, 4.87),
        (52.00, 6.00),  # far — should be trimmed
    ]
    matrix = _matrix_for_points_km(points)
    vehicle = VehicleRoutingInput(
        vehicle_id=1,
        vehicle_code="T1",
        drop_keys=("near1", "near2", "near3", "far"),
        order_ids_per_drop=((1,), (2,), (3,), (4,)),
        drop_weights_kg=(100.0, 100.0, 100.0, 5000.0),
        distance_matrix_m=matrix,
    )
    result = solve_routes(
        RoutingRequest(vehicles=(vehicle,), max_drops_per_route=3, time_limit_s=2.0, seed=1)
    )
    assert len(result.routes) == 1
    route = result.routes[0]
    assert route.drop_count <= 3
    assert 4 in result.unrouted_order_ids
    assert 4 not in route.ordered_order_ids
    assert all(k != "far" for k in route.ordered_drop_keys)


def test_trim_drops_unit() -> None:
    matrix = (
        (0, 100, 200, 300),
        (100, 0, 50, 60),
        (200, 50, 0, 70),
        (300, 60, 70, 0),
    )
    keys, _orders, _w, new_m, unrouted, warn = trim_drops(
        drop_keys=("a", "b", "c"),
        order_ids_per_drop=((1,), (2,), (3,)),
        drop_weights_kg=(10.0, 20.0, 30.0),
        distance_matrix_m=matrix,
        max_drops=2,
    )
    assert len(keys) == 2
    assert set(unrouted) == {3} or len(unrouted) == 1
    assert warn is not None
    assert len(new_m) == 3
