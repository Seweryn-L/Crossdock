"""Golden tests for CP-SAT order→vehicle assignment."""

from __future__ import annotations

from crossdock.optimization.assignment import solve_assignment
from crossdock.optimization.dto import AssignmentRequest, SolverOrder, SolverVehicle


def _bus(**kwargs: object) -> SolverVehicle:
    defaults = dict(
        id=10,
        code="BUS",
        weight_capacity_kg=1050.0,
        pallet_capacity=8,
        kg_per_pallet=131.25,
    )
    defaults.update(kwargs)
    return SolverVehicle(**defaults)  # type: ignore[arg-type]


def _truck(**kwargs: object) -> SolverVehicle:
    defaults = dict(
        id=11,
        code="TRUCK",
        weight_capacity_kg=24500.0,
        pallet_capacity=33,
        kg_per_pallet=24500.0 / 33.0,
    )
    defaults.update(kwargs)
    return SolverVehicle(**defaults)  # type: ignore[arg-type]


def test_small_instance_assigns_without_overload() -> None:
    request = AssignmentRequest(
        orders=(
            SolverOrder(id=1, delivery_code="A", weight_kg=2000),
            SolverOrder(id=2, delivery_code="B", weight_kg=3000),
            SolverOrder(id=3, delivery_code="C", weight_kg=10000),
        ),
        vehicles=(
            _bus(weight_capacity_kg=3500, pallet_capacity=20, kg_per_pallet=175.0),
            _truck(weight_capacity_kg=12000, pallet_capacity=33),
        ),
        time_limit_s=5.0,
        seed=42,
    )
    result = solve_assignment(request)
    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert set(result.assigned_order_ids) | set(result.unassigned_order_ids) == {1, 2, 3}
    assert len(set(result.assigned_order_ids)) == len(result.assigned_order_ids)

    by_code = {load.vehicle_code: load for load in result.loads}
    for load in result.loads:
        assert load.total_weight_kg <= load.capacity_kg + 1e-6
    # Heavy order C must go on TRUCK if assigned.
    if 3 in result.assigned_order_ids:
        assert 3 in by_code["TRUCK"].order_ids


def test_order_exceeding_all_capacities_is_unassigned() -> None:
    request = AssignmentRequest(
        orders=(SolverOrder(id=1, delivery_code="HUGE", weight_kg=50000),),
        vehicles=(_bus(),),
        time_limit_s=2.0,
        seed=1,
    )
    result = solve_assignment(request)
    assert result.unassigned_order_ids == (1,)
    assert result.assigned_order_ids == ()


def test_empty_orders() -> None:
    request = AssignmentRequest(
        orders=(),
        vehicles=(_bus(id=1, code="V1", weight_capacity_kg=1000),),
        time_limit_s=1.0,
        seed=1,
    )
    result = solve_assignment(request)
    assert result.status == "EMPTY"
    assert result.unassigned_order_ids == ()


def test_heavy_order_not_on_bus_via_dual_capacity() -> None:
    """FTL-weight shipment must not ride a bus — kg and pallet constraints both bite."""
    request = AssignmentRequest(
        orders=(
            SolverOrder(id=1, delivery_code="HEAVY", weight_kg=5000.0),
            SolverOrder(id=2, delivery_code="LIGHT", weight_kg=400.0),
        ),
        vehicles=(_bus(id=1), _truck(id=2)),
        time_limit_s=5.0,
        seed=7,
    )
    result = solve_assignment(request)
    by_code = {load.vehicle_code: load for load in result.loads}
    assert 1 in result.assigned_order_ids
    assert 1 in by_code["TRUCK"].order_ids
    bus_load = by_code.get("BUS")
    if bus_load is not None:
        assert 1 not in bus_load.order_ids


def test_assignment_keeps_whole_order_atomic() -> None:
    """FR-019: solver assigns whole SolverOrder ids, never splits an id."""
    request = AssignmentRequest(
        orders=(
            SolverOrder(id=1, delivery_code="PAIR", weight_kg=800.0),
            SolverOrder(id=2, delivery_code="SOLO", weight_kg=400.0),
        ),
        vehicles=(_bus(id=1), _truck(id=2)),
        time_limit_s=5.0,
        seed=4,
    )
    result = solve_assignment(request)
    assigned = list(result.assigned_order_ids)
    assert len(assigned) == len(set(assigned))
    for load in result.loads:
        assert len(load.order_ids) == len(set(load.order_ids))


def test_explicit_pallet_count_blocks_bus() -> None:
    """Known pallet_count > bus slots blocks assignment even when weight fits."""
    request = AssignmentRequest(
        orders=(
            SolverOrder(id=1, delivery_code="MANY", weight_kg=500.0, pallet_count=12),
        ),
        vehicles=(_bus(id=1), _truck(id=2)),
        time_limit_s=5.0,
        seed=3,
    )
    result = solve_assignment(request)
    by_code = {load.vehicle_code: load for load in result.loads}
    assert 1 in by_code["TRUCK"].order_ids
    assert "BUS" not in by_code or 1 not in by_code["BUS"].order_ids
