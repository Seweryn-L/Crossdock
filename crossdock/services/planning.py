"""Planning use case: build assignment request, run CP-SAT, persist result."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from crossdock.config import Settings, get_settings
from crossdock.domain.models import Order, OrderStatus, Vehicle
from crossdock.optimization.assignment import solve_assignment
from crossdock.optimization.dto import (
    AssignmentRequest,
    AssignmentResult,
    SolverOrder,
    SolverVehicle,
)
from crossdock.storage.repositories import (
    AssignmentRepository,
    AuditLogRepository,
    OrderRepository,
    VehicleRepository,
)


@dataclass(frozen=True)
class PlanningOutcome:
    result: AssignmentResult
    run_id: int
    skipped_no_weight: tuple[str, ...]


def orders_to_solver(orders: list[Order]) -> tuple[list[SolverOrder], list[str]]:
    """Map domain orders to solver DTOs; skip those without total weight."""
    solver_orders: list[SolverOrder] = []
    skipped: list[str] = []
    for order in orders:
        if order.id is None:
            continue
        weight = order.total_weight_kg
        if weight is None:
            skipped.append(order.delivery_code)
            continue
        solver_orders.append(
            SolverOrder(
                id=order.id,
                delivery_code=order.delivery_code,
                weight_kg=weight,
            )
        )
    return solver_orders, skipped


def vehicles_to_solver(vehicles: list[Vehicle]) -> list[SolverVehicle]:
    out: list[SolverVehicle] = []
    for vehicle in vehicles:
        if vehicle.id is None:
            continue
        out.append(
            SolverVehicle(
                id=vehicle.id,
                code=vehicle.code,
                weight_capacity_kg=vehicle.weight_capacity_kg,
            )
        )
    return out


class PlanningService:
    def __init__(self, session: Session, *, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()

    def run_assignment(self, *, username: str) -> PlanningOutcome:
        orders = OrderRepository(self._session).list_by_status(OrderStatus.NEW)
        vehicles = VehicleRepository(self._session).list_active()
        solver_orders, skipped = orders_to_solver(orders)
        solver_vehicles = vehicles_to_solver(vehicles)

        request = AssignmentRequest(
            orders=tuple(solver_orders),
            vehicles=tuple(solver_vehicles),
            time_limit_s=self._settings.solver_time_limit_s,
            seed=self._settings.solver_seed,
        )
        result = solve_assignment(request)

        warnings = list(result.warnings)
        if skipped:
            warnings.append(
                f"Pominięto {len(skipped)} zleceń bez wagi (kg): "
                + ", ".join(skipped[:10])
                + ("…" if len(skipped) > 10 else "")
            )
            result = AssignmentResult(
                loads=result.loads,
                unassigned_order_ids=result.unassigned_order_ids,
                status=result.status,
                wall_time_s=result.wall_time_s,
                warnings=tuple(warnings),
            )

        meta = {o.id: (o.delivery_code, o.weight_kg) for o in solver_orders}
        # Also meta for any that somehow appear only in unassigned from other sources
        for order in orders:
            if order.id is not None and order.id not in meta:
                w = order.total_weight_kg or 0.0
                meta[order.id] = (order.delivery_code, w)

        run_id = AssignmentRepository(self._session).save_run(
            username=username,
            status=result.status,
            wall_time_s=result.wall_time_s,
            warnings=list(result.warnings),
            loads=[
                {
                    "vehicle_id": load.vehicle_id,
                    "vehicle_code": load.vehicle_code,
                    "order_ids": list(load.order_ids),
                    "fill_ratio": load.fill_ratio,
                }
                for load in result.loads
            ],
            unassigned_order_ids=list(result.unassigned_order_ids),
            order_meta=meta,
        )
        AuditLogRepository(self._session).record(
            username=username,
            action="planning.assignment",
            details={
                "run_id": run_id,
                "status": result.status,
                "assigned": len(result.assigned_order_ids),
                "unassigned": len(result.unassigned_order_ids),
                "wall_time_s": round(result.wall_time_s, 3),
            },
        )
        return PlanningOutcome(
            result=result,
            run_id=run_id,
            skipped_no_weight=tuple(skipped),
        )
