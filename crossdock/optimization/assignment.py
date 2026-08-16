"""CP-SAT assignment of orders to heterogeneous vehicles (T3).

Pure optimization: no I/O. Assigns whole orders (FR-019) maximizing
total assigned weight (FR-011 fill), subject to kg and pallet capacities.
"""

from __future__ import annotations

import time

from ortools.sat.python import cp_model

from crossdock.domain.pallet_estimate import resolve_pallet_demand
from crossdock.optimization.dto import (
    AssignmentRequest,
    AssignmentResult,
    SolverOrder,
    SolverVehicle,
    VehicleLoad,
)

# OR-Tools CP-SAT works on integers; scale kg to grams.
_WEIGHT_SCALE = 1000


def _pallet_demand(order: SolverOrder, vehicle: SolverVehicle) -> int:
    """Pallets required if ``order`` is loaded on ``vehicle``."""
    demand = resolve_pallet_demand(
        order.weight_kg,
        explicit_pallets=order.pallet_count,
        vehicle_kg_per_pallet=vehicle.kg_per_pallet,
    )
    return 0 if demand is None else demand


def _fits_vehicle(order: SolverOrder, vehicle: SolverVehicle) -> bool:
    if order.weight_kg > vehicle.weight_capacity_kg:
        return False
    return _pallet_demand(order, vehicle) <= vehicle.pallet_capacity


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

    # Drop orders that cannot fit any vehicle alone (kg or pallets).
    eligible: list[SolverOrder] = []
    forced_unassigned: list[int] = []
    for order in request.orders:
        if order.weight_kg <= 0:
            forced_unassigned.append(order.id)
            warnings.append(f"Zlecenie {order.delivery_code}: waga ≤ 0 — pominięte.")
            continue
        if not any(_fits_vehicle(order, v) for v in request.vehicles):
            forced_unassigned.append(order.id)
            max_cap = max(v.weight_capacity_kg for v in request.vehicles)
            warnings.append(
                f"Zlecenie {order.delivery_code}: waga {order.weight_kg:.0f} kg "
                f"(lub szacunek palet) nie mieści się w żadnym pojeździe "
                f"(max {max_cap:.0f} kg)."
            )
            continue
        eligible.append(order)

    order_ids = [o.id for o in eligible]
    weights = [round(o.weight_kg * _WEIGHT_SCALE) for o in eligible]
    n_o = len(order_ids)
    n_v = len(request.vehicles)
    caps = [round(v.weight_capacity_kg * _WEIGHT_SCALE) for v in request.vehicles]
    pallet_caps = [int(v.pallet_capacity) for v in request.vehicles]
    # pallet_demand[o][v]
    pallet_demand = [
        [_pallet_demand(order, vehicle) for vehicle in request.vehicles] for order in eligible
    ]

    if n_o == 0:
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
            # Forbid pairs that exceed this vehicle alone.
            if not _fits_vehicle(eligible[o], request.vehicles[v]):
                # Fixed to 0 — still create var for uniform indexing.
                x[o, v] = model.new_constant(0)
            else:
                x[o, v] = model.new_bool_var(f"x_{o}_{v}")

    # Each order on at most one vehicle.
    for o in range(n_o):
        model.add(sum(x[o, v] for v in range(n_v)) <= 1)

    # Capacity per vehicle: kg and pallets.
    for v in range(n_v):
        model.add(sum(weights[o] * x[o, v] for o in range(n_o)) <= caps[v])
        model.add(sum(pallet_demand[o][v] * x[o, v] for o in range(n_o)) <= pallet_caps[v])

    # Maximize assigned weight (FR-011).
    model.maximize(sum(weights[o] * x[o, v] for o in range(n_o) for v in range(n_v)))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(request.time_limit_s)
    solver.parameters.random_seed = int(request.seed)
    # Keep pool warm-friendly on Windows; single worker is fine at this scale.
    solver.parameters.num_search_workers = 4

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
    return AssignmentResult(
        loads=tuple(loads),
        unassigned_order_ids=unassigned,
        status=status_name,
        wall_time_s=time.perf_counter() - started,
        warnings=tuple(warnings),
    )
