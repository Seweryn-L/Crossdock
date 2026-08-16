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


def test_max_drops_per_route_leaves_extra_city_unassigned() -> None:
    request = AssignmentRequest(
        orders=(
            SolverOrder(id=1, delivery_code="A", weight_kg=1000, drop_key="paris"),
            SolverOrder(id=2, delivery_code="B", weight_kg=1000, drop_key="brussels"),
            SolverOrder(id=3, delivery_code="C", weight_kg=1000, drop_key="rotterdam"),
            SolverOrder(id=4, delivery_code="D", weight_kg=1000, drop_key="berlin"),
        ),
        vehicles=(SolverVehicle(id=1, code="T1", weight_capacity_kg=12000),),
        time_limit_s=5.0,
        seed=42,
        max_drops_per_route=3,
    )
    result = solve_assignment(request)
    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert len(result.assigned_order_ids) == 3
    assert len(result.unassigned_order_ids) == 1
    assigned_keys = {o.drop_key for o in request.orders if o.id in set(result.assigned_order_ids)}
    assert len(assigned_keys) == 3


def test_assignment_is_reproducible_with_same_seed() -> None:
    request = AssignmentRequest(
        orders=(
            SolverOrder(id=1, delivery_code="A", weight_kg=2000, drop_key="p"),
            SolverOrder(id=2, delivery_code="B", weight_kg=3000, drop_key="b"),
            SolverOrder(id=3, delivery_code="C", weight_kg=2500, drop_key="r"),
        ),
        vehicles=(
            SolverVehicle(id=10, code="T1", weight_capacity_kg=4000),
            SolverVehicle(id=11, code="T2", weight_capacity_kg=4000),
        ),
        time_limit_s=5.0,
        seed=42,
        max_drops_per_route=3,
    )
    first = solve_assignment(request)
    second = solve_assignment(request)
    assert first.assigned_order_ids == second.assigned_order_ids
    assert [load.order_ids for load in first.loads] == [load.order_ids for load in second.loads]


def test_must_ship_beats_heavier_optional() -> None:
    request = AssignmentRequest(
        orders=(
            SolverOrder(id=1, delivery_code="OPTIONAL", weight_kg=2500, must_ship=False),
            SolverOrder(id=2, delivery_code="MUST", weight_kg=2000, must_ship=True),
        ),
        vehicles=(SolverVehicle(id=1, code="T1", weight_capacity_kg=3000),),
        time_limit_s=5.0,
        seed=42,
    )
    result = solve_assignment(request)
    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert 2 in result.assigned_order_ids
    assert 1 in result.unassigned_order_ids


def test_unassigned_must_ship_is_warned() -> None:
    request = AssignmentRequest(
        orders=(SolverOrder(id=1, delivery_code="MUST", weight_kg=9000, must_ship=True),),
        vehicles=(SolverVehicle(id=1, code="BUS", weight_capacity_kg=3500),),
        time_limit_s=2.0,
        seed=1,
    )
    result = solve_assignment(request)
    assert 1 in result.unassigned_order_ids
    assert any("muszą wyjechać dziś" in w for w in result.warnings)


def test_overdue_orders_are_warned() -> None:
    request = AssignmentRequest(
        orders=(
            SolverOrder(id=1, delivery_code="LATE", weight_kg=1000, overdue=True, must_ship=True),
        ),
        vehicles=(SolverVehicle(id=1, code="T1", weight_capacity_kg=3500),),
        time_limit_s=2.0,
        seed=1,
        ship_lead_days=2,
    )
    result = solve_assignment(request)
    assert any("Spóźnione" in w for w in result.warnings)


def test_empty_orders_status() -> None:
    request = AssignmentRequest(
        orders=(),
        vehicles=(SolverVehicle(id=1, code="V1", weight_capacity_kg=1000),),
        time_limit_s=1.0,
        seed=1,
    )
    result = solve_assignment(request)
    assert result.status == "EMPTY"
    assert result.unassigned_order_ids == ()
