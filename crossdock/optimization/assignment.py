"""CP-SAT assignment of orders to heterogeneous vehicles (T3).

Pure optimization: no I/O. Assigns whole orders (FR-019) maximizing
total assigned weight (FR-011 fill), subject to kg capacities.
"""

from __future__ import annotations

import time

from ortools.sat.python import cp_model

from crossdock.optimization.dto import (
    AssignmentRequest,
    AssignmentResult,
    SolverOrder,
    VehicleLoad,
)

# OR-Tools CP-SAT works on integers; scale kg to grams.
_WEIGHT_SCALE = 1000
# Must-ship orders (last legal departure / queue / overflow) beat heavier optional ones.
_URGENT_BONUS = 100


def solve_assignment(request: AssignmentRequest) -> AssignmentResult:
    """Solve order→vehicle assignment; safe to call from run.cpu_bound."""
    started = time.perf_counter()
    warnings: list[str] = []

    if not request.vehicles:
        return AssignmentResult(
            loads=(),
            unassigned_order_ids=tuple(o.id for o in request.orders),
            status="NO_VEHICLES",
            wall_time_s=time.perf_counter() - started,
            warnings=("Brak aktywnych pojazdów we flocie.",),
        )

    if not request.orders:
        return AssignmentResult(
            loads=tuple(
                VehicleLoad(
                    vehicle_id=v.id,
                    vehicle_code=v.code,
                    order_ids=(),
                    total_weight_kg=0.0,
                    capacity_kg=v.weight_capacity_kg,
                )
                for v in request.vehicles
            ),
            unassigned_order_ids=(),
            status="EMPTY",
            wall_time_s=time.perf_counter() - started,
        )

    # Drop orders that cannot fit any vehicle alone.
    eligible: list[tuple[int, int]] = []  # (order_index, weight_scaled)
    forced_unassigned: list[int] = []
    max_cap = max(v.weight_capacity_kg for v in request.vehicles)
    for order in request.orders:
        if order.weight_kg <= 0:
            forced_unassigned.append(order.id)
            warnings.append(f"Zlecenie {order.delivery_code}: waga ≤ 0 — pominięte.")
            continue
        if order.weight_kg > max_cap:
            forced_unassigned.append(order.id)
            warnings.append(
                f"Zlecenie {order.delivery_code}: waga {order.weight_kg:.0f} kg "
                f"przekracza największy pojazd ({max_cap:.0f} kg)."
            )
            continue
        eligible.append((order.id, round(order.weight_kg * _WEIGHT_SCALE)))

    order_ids = [oid for oid, _ in eligible]
    weights = [w for _, w in eligible]
    n_o = len(order_ids)
    n_v = len(request.vehicles)
    caps = [round(v.weight_capacity_kg * _WEIGHT_SCALE) for v in request.vehicles]
    by_id = {order.id: order for order in request.orders}

    if n_o == 0:
        _append_sla_warnings(warnings, request, tuple(forced_unassigned), by_id)
        return AssignmentResult(
            loads=tuple(
                VehicleLoad(
                    vehicle_id=v.id,
                    vehicle_code=v.code,
                    order_ids=(),
                    total_weight_kg=0.0,
                    capacity_kg=v.weight_capacity_kg,
                )
                for v in request.vehicles
            ),
            unassigned_order_ids=tuple(forced_unassigned),
            status="NO_ELIGIBLE_ORDERS",
            wall_time_s=time.perf_counter() - started,
            warnings=tuple(warnings),
        )

    model = cp_model.CpModel()
    x: dict[tuple[int, int], cp_model.IntVar] = {}
    for o in range(n_o):
        for v in range(n_v):
            x[o, v] = model.new_bool_var(f"x_{o}_{v}")

    # Each order on at most one vehicle.
    for o in range(n_o):
        model.add(sum(x[o, v] for v in range(n_v)) <= 1)

    # Capacity per vehicle.
    for v in range(n_v):
        model.add(sum(weights[o] * x[o, v] for o in range(n_o)) <= caps[v])

    max_drops = int(request.max_drops_per_route)
    if max_drops >= 1:
        drop_keys = [(by_id[oid].drop_key or f"__order_{oid}") for oid in order_ids]
        unique_keys = sorted(set(drop_keys))
        key_index = {key: idx for idx, key in enumerate(unique_keys)}
        used: dict[tuple[int, int], cp_model.IntVar] = {}
        for d_idx in range(len(unique_keys)):
            for v in range(n_v):
                used[d_idx, v] = model.new_bool_var(f"used_{d_idx}_{v}")
        for o in range(n_o):
            d_idx = key_index[drop_keys[o]]
            for v in range(n_v):
                model.add(x[o, v] <= used[d_idx, v])
        for v in range(n_v):
            model.add(sum(used[d, v] for d in range(len(unique_keys))) <= max_drops)

    # Maximize assigned weight (FR-011); must-ship kg counts much more.
    objective_terms = []
    for o in range(n_o):
        bonus = 1 + (_URGENT_BONUS if by_id[order_ids[o]].must_ship else 0)
        for v in range(n_v):
            objective_terms.append(bonus * weights[o] * x[o, v])
    model.maximize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(request.time_limit_s)
    solver.parameters.random_seed = int(request.seed)
    # Single worker: reproducible results at this scale (AGENTS.md seed).
    solver.parameters.num_search_workers = 1

    status_code = solver.solve(model)
    status_name = solver.status_name(status_code)

    loads: list[VehicleLoad] = []
    assigned: set[int] = set()
    if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for v_idx, vehicle in enumerate(request.vehicles):
            vids: list[int] = []
            total = 0.0
            for o_idx, oid in enumerate(order_ids):
                if solver.value(x[o_idx, v_idx]) == 1:
                    vids.append(oid)
                    assigned.add(oid)
                    total += weights[o_idx] / _WEIGHT_SCALE
            loads.append(
                VehicleLoad(
                    vehicle_id=vehicle.id,
                    vehicle_code=vehicle.code,
                    order_ids=tuple(vids),
                    total_weight_kg=total,
                    capacity_kg=vehicle.weight_capacity_kg,
                )
            )
    else:
        warnings.append(f"Solver nie znalazł rozwiązania ({status_name}).")
        loads = [
            VehicleLoad(
                vehicle_id=v.id,
                vehicle_code=v.code,
                order_ids=(),
                total_weight_kg=0.0,
                capacity_kg=v.weight_capacity_kg,
            )
            for v in request.vehicles
        ]

    unassigned = tuple(forced_unassigned + [oid for oid in order_ids if oid not in assigned])
    _append_sla_warnings(warnings, request, unassigned, by_id)
    return AssignmentResult(
        loads=tuple(loads),
        unassigned_order_ids=unassigned,
        status=status_name,
        wall_time_s=time.perf_counter() - started,
        warnings=tuple(warnings),
    )


def _append_sla_warnings(
    warnings: list[str],
    request: AssignmentRequest,
    unassigned: tuple[int, ...],
    by_id: dict[int, SolverOrder],
) -> None:
    overdue_codes = [o.delivery_code for o in request.orders if o.overdue]
    if overdue_codes:
        warnings.append(
            f"Spóźnione (wyjazd po terminie-{request.ship_lead_days} dni): "
            f"{len(overdue_codes)}"
            + (": " + ", ".join(overdue_codes[:10]) if overdue_codes else "")
            + ("…" if len(overdue_codes) > 10 else "")
        )
    missed = [
        by_id[oid].delivery_code for oid in unassigned if oid in by_id and by_id[oid].must_ship
    ]
    if missed:
        warnings.append(
            "Nie przydzielono zleceń, które muszą wyjechać dziś: "
            + ", ".join(missed[:10])
            + ("…" if len(missed) > 10 else "")
        )
