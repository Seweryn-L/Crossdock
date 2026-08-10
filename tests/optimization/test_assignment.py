"""Golden tests for CP-SAT order→vehicle assignment."""

from __future__ import annotations

from crossdock.optimization.assignment import solve_assignment
from crossdock.optimization.dto import AssignmentRequest, SolverOrder, SolverVehicle


def test_small_instance_assigns_without_overload() -> None:
    request = AssignmentRequest(
        orders=(
            SolverOrder(id=1, delivery_code="A", weight_kg=2000),
            SolverOrder(id=2, delivery_code="B", weight_kg=3000),
            SolverOrder(id=3, delivery_code="C", weight_kg=10000),
        ),
        vehicles=(
            SolverVehicle(id=10, code="BUS", weight_capacity_kg=3500),
            SolverVehicle(id=11, code="TRUCK", weight_capacity_kg=12000),
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
        vehicles=(SolverVehicle(id=1, code="BUS", weight_capacity_kg=3500),),
        time_limit_s=2.0,
        seed=1,
    )
    result = solve_assignment(request)
    assert result.unassigned_order_ids == (1,)
    assert result.assigned_order_ids == ()


def test_empty_orders() -> None:
    request = AssignmentRequest(
        orders=(),
        vehicles=(SolverVehicle(id=1, code="V1", weight_capacity_kg=1000),),
        time_limit_s=1.0,
        seed=1,
    )
    result = solve_assignment(request)
    assert result.status == "EMPTY"
    assert result.unassigned_order_ids == ()
