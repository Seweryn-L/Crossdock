"""Property-based invariants for assignment solver (hypothesis)."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from crossdock.optimization.assignment import solve_assignment
from crossdock.optimization.dto import AssignmentRequest, SolverOrder, SolverVehicle


@st.composite
def assignment_instances(draw: st.DrawFn) -> AssignmentRequest:
    n_orders = draw(st.integers(min_value=0, max_value=12))
    n_vehicles = draw(st.integers(min_value=1, max_value=5))
    orders = tuple(
        SolverOrder(
            id=i + 1,
            delivery_code=f"O{i + 1}",
            weight_kg=draw(
                st.floats(
                    min_value=100,
                    max_value=20000,
                    allow_nan=False,
                    allow_infinity=False,
                )
            ),
            drop_key=draw(st.sampled_from(["A", "B", "C", "D", None])),
        )
        for i in range(n_orders)
    )
    vehicles = tuple(
        SolverVehicle(
            id=100 + j,
            code=f"V{j + 1}",
            weight_capacity_kg=draw(
                st.floats(
                    min_value=2000,
                    max_value=24000,
                    allow_nan=False,
                    allow_infinity=False,
                )
            ),
        )
        for j in range(n_vehicles)
    )
    return AssignmentRequest(
        orders=orders,
        vehicles=vehicles,
        time_limit_s=2.0,
        seed=draw(st.integers(min_value=0, max_value=10_000)),
        max_drops_per_route=draw(st.integers(min_value=0, max_value=3)),
    )


@given(assignment_instances())
@settings(max_examples=40, deadline=None)
def test_assignment_invariants(request: AssignmentRequest) -> None:
    result = solve_assignment(request)
    input_ids = {o.id for o in request.orders}
    assigned = list(result.assigned_order_ids)
    assert len(assigned) == len(set(assigned))
    assert set(assigned).isdisjoint(result.unassigned_order_ids)
    assert set(assigned) | set(result.unassigned_order_ids) == input_ids

    weights = {o.id: o.weight_kg for o in request.orders}
    orders_by_id = {o.id: o for o in request.orders}
    for load in result.loads:
        total = sum(weights[oid] for oid in load.order_ids)
        assert total <= load.capacity_kg + 1.0  # 1 kg tolerance for rounding
        assert abs(total - load.total_weight_kg) < 1.0
        if request.max_drops_per_route >= 1:
            keys = {(orders_by_id[oid].drop_key or f"__order_{oid}") for oid in load.order_ids}
            assert len(keys) <= request.max_drops_per_route
