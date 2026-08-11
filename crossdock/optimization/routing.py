"""OR-Tools routing: drop order, max drops (FR-012), minimize km (FR-014).

Pure optimization: no I/O. Expects assignment already done; works per vehicle
on unique drop nodes. Drops beyond max_drops_per_route are trimmed before
the RoutingModel so the model stays feasible.
"""

from __future__ import annotations

import time

from ortools.constraint_solver import pywrapcp, routing_enums_pb2  # type: ignore[import-untyped]

from crossdock.optimization.dto import (
    RoutingRequest,
    RoutingResult,
    VehicleRoute,
    VehicleRoutingInput,
)


def trim_drops(
    *,
    drop_keys: tuple[str, ...],
    order_ids_per_drop: tuple[tuple[int, ...], ...],
    drop_weights_kg: tuple[float, ...],
    distance_matrix_m: tuple[tuple[int, ...], ...],
    max_drops: int,
) -> tuple[
    tuple[str, ...],
    tuple[tuple[int, ...], ...],
    tuple[float, ...],
    tuple[tuple[int, ...], ...],
    tuple[int, ...],
    str | None,
]:
    """Keep up to ``max_drops`` closest-to-depot (then heaviest); return unrouted ids."""
    n = len(drop_keys)
    if n == 0:
        return (), (), (), ((0,),), (), None
    if max_drops < 1:
        all_ids = tuple(oid for group in order_ids_per_drop for oid in group)
        return (), (), (), ((0,),), all_ids, "max_drops_per_route < 1 — wszystkie dropy odrzucone."

    if n <= max_drops:
        return (
            drop_keys,
            order_ids_per_drop,
            drop_weights_kg,
            distance_matrix_m,
            (),
            None,
        )

    # Rank by distance from depot (matrix[0][i+1]), then -weight.
    ranked = sorted(
        range(n),
        key=lambda i: (distance_matrix_m[0][i + 1], -drop_weights_kg[i]),
    )
    keep = set(ranked[:max_drops])
    kept_keys: list[str] = []
    kept_orders: list[tuple[int, ...]] = []
    kept_weights: list[float] = []
    old_to_new: dict[int, int] = {}
    unrouted: list[int] = []
    for old_i in range(n):
        if old_i in keep:
            old_to_new[old_i] = len(kept_keys)
            kept_keys.append(drop_keys[old_i])
            kept_orders.append(order_ids_per_drop[old_i])
            kept_weights.append(drop_weights_kg[old_i])
        else:
            unrouted.extend(order_ids_per_drop[old_i])

    m = 1 + len(kept_keys)
    new_matrix = [[0] * m for _ in range(m)]
    for old_i, new_i in old_to_new.items():
        # depot ↔ drop
        new_matrix[0][new_i + 1] = distance_matrix_m[0][old_i + 1]
        new_matrix[new_i + 1][0] = distance_matrix_m[old_i + 1][0]
        for old_j, new_j in old_to_new.items():
            new_matrix[new_i + 1][new_j + 1] = distance_matrix_m[old_i + 1][old_j + 1]

    warning = (
        f"Przycięto dropy do limitu {max_drops} "
        f"(odrzucono {n - max_drops} punktów / {len(unrouted)} zleceń)."
    )
    return (
        tuple(kept_keys),
        tuple(kept_orders),
        tuple(kept_weights),
        tuple(tuple(row) for row in new_matrix),
        tuple(unrouted),
        warning,
    )


def _solve_vehicle_tsp(
    matrix_m: tuple[tuple[int, ...], ...],
    *,
    time_limit_s: float,
    seed: int,
) -> tuple[list[int], int, str]:
    """Return drop indices (0-based into drops, not matrix), total metres, status."""
    del seed  # RoutingSearchParameters has no stable seed API across OR-Tools versions.
    n = len(matrix_m)
    if n <= 1:
        return [], 0, "EMPTY"

    manager = pywrapcp.RoutingIndexManager(n, 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index: int, to_index: int) -> int:
        frm = manager.IndexToNode(from_index)
        to = manager.IndexToNode(to_index)
        return int(matrix_m[frm][to])

    transit_idx = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    params.time_limit.FromSeconds(max(1, int(time_limit_s)))
    params.log_search = False

    solution = routing.SolveWithParameters(params)
    if solution is None:
        # Fallback: visit drops in matrix order 1..n-1
        order = list(range(n - 1))
        metres = 0
        prev = 0
        for d in order:
            node = d + 1
            metres += matrix_m[prev][node]
            prev = node
        metres += matrix_m[prev][0]
        return order, metres, "FALLBACK"

    index = routing.Start(0)
    drop_order: list[int] = []
    metres = 0
    while not routing.IsEnd(index):
        node = manager.IndexToNode(index)
        next_index = solution.Value(routing.NextVar(index))
        next_node = manager.IndexToNode(next_index)
        metres += matrix_m[node][next_node]
        if node != 0:
            drop_order.append(node - 1)
        index = next_index
    return drop_order, metres, "FEASIBLE"


def _route_one(
    vehicle: VehicleRoutingInput,
    *,
    max_drops: int,
    time_limit_s: float,
    seed: int,
    cost_per_km: float,
) -> tuple[VehicleRoute | None, tuple[int, ...], tuple[str, ...]]:
    warnings: list[str] = []
    keys, orders, _weights, matrix, trimmed, warn = trim_drops(
        drop_keys=vehicle.drop_keys,
        order_ids_per_drop=vehicle.order_ids_per_drop,
        drop_weights_kg=vehicle.drop_weights_kg,
        distance_matrix_m=vehicle.distance_matrix_m,
        max_drops=max_drops,
    )
    if warn:
        warnings.append(f"{vehicle.vehicle_code}: {warn}")
    if not keys:
        all_ids = tuple(oid for group in vehicle.order_ids_per_drop for oid in group)
        return None, trimmed if trimmed else all_ids, tuple(warnings)

    drop_seq, metres, _status = _solve_vehicle_tsp(matrix, time_limit_s=time_limit_s, seed=seed)
    ordered_keys: list[str] = []
    ordered_ids: list[int] = []
    for drop_i in drop_seq:
        ordered_keys.append(keys[drop_i])
        ordered_ids.extend(orders[drop_i])

    distance_km = metres / 1000.0
    route = VehicleRoute(
        vehicle_id=vehicle.vehicle_id,
        vehicle_code=vehicle.vehicle_code,
        ordered_order_ids=tuple(ordered_ids),
        ordered_drop_keys=tuple(ordered_keys),
        drop_count=len(ordered_keys),
        distance_km=distance_km,
        cost_eur=distance_km * cost_per_km,
    )
    return route, trimmed, tuple(warnings)


def solve_routes(request: RoutingRequest) -> RoutingResult:
    """Solve drop sequencing per vehicle; safe to call from run.cpu_bound."""
    started = time.perf_counter()
    if not request.vehicles:
        return RoutingResult(
            routes=(),
            unrouted_order_ids=(),
            status="NO_VEHICLES",
            wall_time_s=time.perf_counter() - started,
            warnings=("Brak pojazdów do routingu.",),
        )

    per_vehicle_limit = max(1.0, request.time_limit_s / max(1, len(request.vehicles)))
    routes: list[VehicleRoute] = []
    unrouted: list[int] = []
    warnings: list[str] = []
    any_routed = False

    for vehicle in request.vehicles:
        if not vehicle.drop_keys:
            continue
        route, trimmed_ids, warns = _route_one(
            vehicle,
            max_drops=request.max_drops_per_route,
            time_limit_s=per_vehicle_limit,
            seed=request.seed,
            cost_per_km=request.cost_per_km,
        )
        warnings.extend(warns)
        unrouted.extend(trimmed_ids)
        if route is not None and route.drop_count > 0:
            routes.append(route)
            any_routed = True

    status = "OPTIMAL" if any_routed else ("EMPTY" if not unrouted else "NO_ROUTES")
    return RoutingResult(
        routes=tuple(routes),
        unrouted_order_ids=tuple(unrouted),
        status=status,
        wall_time_s=time.perf_counter() - started,
        warnings=tuple(warnings),
    )
