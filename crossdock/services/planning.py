"""Planning use cases: assignment + routing + plan approval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from crossdock.config import Settings, get_settings
from crossdock.distance.haversine import HaversineDistanceProvider
from crossdock.domain.models import Location, Order, OrderStatus, Vehicle
from crossdock.optimization.assignment import solve_assignment
from crossdock.optimization.dto import (
    AssignmentRequest,
    AssignmentResult,
    PlanResult,
    RoutingRequest,
    SolverOrder,
    SolverVehicle,
    VehicleRoutingInput,
)
from crossdock.optimization.routing import solve_routes
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


@dataclass(frozen=True)
class PlanOutcome:
    plan: PlanResult
    run_id: int
    skipped_no_weight: tuple[str, ...]
    skipped_no_coords: tuple[str, ...]
    planned_order_ids: tuple[int, ...]


@dataclass(frozen=True)
class ApproveOutcome:
    run_id: int
    approved_order_ids: tuple[int, ...]
    vehicle_id: int | None = None
    vehicle_code: str | None = None


@dataclass(frozen=True)
class UnlockOutcome:
    run_id: int
    reset_order_ids: tuple[int, ...]
    vehicle_id: int | None = None
    vehicle_code: str | None = None


@dataclass(frozen=True)
class DeletePlanOutcome:
    run_id: int
    reset_order_ids: tuple[int, ...]


def orders_to_solver(orders: list[Order]) -> tuple[list[SolverOrder], list[str]]:
    """Map domain orders to solver DTOs; skip those without total weight."""
    from crossdock.domain.pallet_estimate import resolve_pallet_demand

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
                pallet_count=resolve_pallet_demand(
                    weight,
                    explicit_pallets=order.total_pallets,
                    cargo_kg_per_pallet=order.kg_per_pallet,
                ),
            )
        )
    return solver_orders, skipped


def vehicles_to_solver(
    vehicles: list[Vehicle], settings: Settings | None = None
) -> list[SolverVehicle]:
    from crossdock.services.pallet_demand import type_kg_per_pallet

    out: list[SolverVehicle] = []
    for vehicle in vehicles:
        if vehicle.id is None:
            continue
        out.append(
            SolverVehicle(
                id=vehicle.id,
                code=vehicle.code,
                weight_capacity_kg=vehicle.weight_capacity_kg,
                pallet_capacity=vehicle.pallet_capacity,
                kg_per_pallet=type_kg_per_pallet(vehicle.vehicle_type, settings),
            )
        )
    return out


def drop_key_for_location(location: Location) -> str | None:
    if location.latitude is not None and location.longitude is not None:
        return f"{location.latitude:.4f}|{location.longitude:.4f}"
    city = (location.city or "").strip()
    country = (location.country or "").strip()
    name = (location.name or "").strip()
    if city or country or name:
        return f"{city}|{country}|{name}"
    return None


def _build_routing_inputs(
    *,
    loads: list[Any],
    orders_by_id: dict[int, Order],
    depot: tuple[float, float],
    distance: HaversineDistanceProvider,
) -> tuple[list[VehicleRoutingInput], list[str], set[int]]:
    """Group assigned orders into drop nodes; skip orders without usable coords."""
    skipped_codes: list[str] = []
    no_coords_ids: set[int] = set()
    vehicles_out: list[VehicleRoutingInput] = []

    for load in loads:
        if not load.order_ids:
            continue
        # drop_key -> (lat, lon, order_ids, weight)
        drops: dict[str, tuple[float, float, list[int], float]] = {}
        for oid in load.order_ids:
            order = orders_by_id.get(oid)
            if order is None:
                continue
            loc = order.delivery_location
            if loc.latitude is None or loc.longitude is None:
                skipped_codes.append(order.delivery_code)
                no_coords_ids.add(oid)
                continue
            key = drop_key_for_location(loc)
            if key is None:
                skipped_codes.append(order.delivery_code)
                no_coords_ids.add(oid)
                continue
            weight = order.total_weight_kg or 0.0
            if key not in drops:
                drops[key] = (loc.latitude, loc.longitude, [oid], weight)
            else:
                lat, lon, ids, w = drops[key]
                ids.append(oid)
                drops[key] = (lat, lon, ids, w + weight)

        if not drops:
            continue

        keys = list(drops.keys())
        points: list[tuple[float, float]] = [depot] + [(drops[k][0], drops[k][1]) for k in keys]
        matrix_km = distance.distance_matrix(points)
        matrix_m = tuple(
            tuple(round(float(matrix_km[i, j]) * 1000) for j in range(len(points)))
            for i in range(len(points))
        )
        vehicles_out.append(
            VehicleRoutingInput(
                vehicle_id=load.vehicle_id,
                vehicle_code=load.vehicle_code,
                drop_keys=tuple(keys),
                order_ids_per_drop=tuple(tuple(drops[k][2]) for k in keys),
                drop_weights_kg=tuple(drops[k][3] for k in keys),
                distance_matrix_m=matrix_m,
            )
        )
    return vehicles_out, skipped_codes, no_coords_ids


class PlanningService:
    def __init__(self, session: Session, *, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()

    def run_assignment(self, *, username: str) -> PlanningOutcome:
        orders = OrderRepository(self._session).list_by_status(OrderStatus.NEW)
        vehicles = VehicleRepository(self._session).list_active()
        solver_orders, skipped = orders_to_solver(orders)
        solver_vehicles = vehicles_to_solver(vehicles, self._settings)

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

    def run_plan(self, *, username: str) -> PlanOutcome:
        repo = AssignmentRepository(self._session)
        vehicle_repo = VehicleRepository(self._session)
        order_repo = OrderRepository(self._session)

        run = repo.ensure_open_run(username=username)
        # Drop previous proposals; keep approved routes. Return those orders to NEW.
        cleared = repo.clear_proposed(run.id)
        if cleared:
            # Only reset orders that are still PLANNED (not APPROVED on other routes).
            to_reset: list[int] = []
            for oid in cleared:
                order = order_repo.get_by_id(oid)
                if order is not None and order.status == OrderStatus.PLANNED:
                    to_reset.append(oid)
            if to_reset:
                order_repo.set_status_many(to_reset, OrderStatus.NEW)

        orders = order_repo.list_by_status(OrderStatus.NEW)
        vehicles = vehicle_repo.list_available()
        solver_orders, skipped_weight = orders_to_solver(orders)
        solver_vehicles = vehicles_to_solver(vehicles, self._settings)
        orders_by_id = {o.id: o for o in orders if o.id is not None}

        if not solver_vehicles:
            raise ValueError("Brak wolnych pojazdów — zatwierdź mniej tras lub dodaj flotę.")
        if not solver_orders:
            raise ValueError("Brak zleceń ze statusem „nowe” i wagą do zaplanowania.")

        total_limit = self._settings.solver_time_limit_s
        assignment_limit = max(5.0, total_limit * 0.4)
        routing_limit = max(5.0, total_limit * 0.6)

        assignment = solve_assignment(
            AssignmentRequest(
                orders=tuple(solver_orders),
                vehicles=tuple(solver_vehicles),
                time_limit_s=assignment_limit,
                seed=self._settings.solver_seed,
            )
        )

        depot = (self._settings.depot_latitude, self._settings.depot_longitude)
        distance = HaversineDistanceProvider()
        routing_inputs, skipped_coord_codes, no_coords_ids = _build_routing_inputs(
            loads=list(assignment.loads),
            orders_by_id=orders_by_id,
            depot=depot,
            distance=distance,
        )

        routing = solve_routes(
            RoutingRequest(
                vehicles=tuple(routing_inputs),
                max_drops_per_route=self._settings.max_drops_per_route,
                time_limit_s=routing_limit,
                seed=self._settings.solver_seed,
                cost_per_km=self._settings.cost_per_km,
            )
        )

        warnings = list(assignment.warnings) + list(routing.warnings)
        if skipped_weight:
            warnings.append(
                f"Pominięto {len(skipped_weight)} zleceń bez wagi (kg): "
                + ", ".join(skipped_weight[:10])
                + ("…" if len(skipped_weight) > 10 else "")
            )
        if skipped_coord_codes:
            warnings.append(
                f"Brak współrzędnych dla {len(skipped_coord_codes)} zleceń "
                f"(bez trasy): "
                + ", ".join(skipped_coord_codes[:10])
                + ("…" if len(skipped_coord_codes) > 10 else "")
            )

        assignment = AssignmentResult(
            loads=assignment.loads,
            unassigned_order_ids=assignment.unassigned_order_ids,
            status=assignment.status,
            wall_time_s=assignment.wall_time_s,
            warnings=tuple(warnings),
        )
        plan = PlanResult(assignment=assignment, routing=routing)

        fill_by_vehicle = {load.vehicle_id: load.fill_ratio for load in assignment.loads}
        sequence_by_order: dict[int, tuple[int, str, int, str]] = {}
        for route in routing.routes:
            seq = 1
            drop_for_order: dict[int, str] = {}
            for vin in routing_inputs:
                if vin.vehicle_id != route.vehicle_id:
                    continue
                key_by_oid: dict[int, str] = {}
                for key, oids in zip(vin.drop_keys, vin.order_ids_per_drop, strict=True):
                    for oid in oids:
                        key_by_oid[oid] = key
                for oid in route.ordered_order_ids:
                    drop_for_order[oid] = key_by_oid.get(oid, "?")
            for oid in route.ordered_order_ids:
                sequence_by_order[oid] = (
                    route.vehicle_id,
                    route.vehicle_code,
                    seq,
                    drop_for_order.get(oid, "?"),
                )
                seq += 1

        routed_ids = set(sequence_by_order)
        unrouted_ids = set(routing.unrouted_order_ids) | no_coords_ids
        unassigned_ids = list(assignment.unassigned_order_ids)

        items: list[dict[str, Any]] = []
        for load in assignment.loads:
            for oid in load.order_ids:
                if oid in routed_ids:
                    vid, vcode, seq, dkey = sequence_by_order[oid]
                    items.append(
                        {
                            "vehicle_id": vid,
                            "vehicle_code": vcode,
                            "order_id": oid,
                            "fill_ratio": fill_by_vehicle.get(load.vehicle_id),
                            "sequence": seq,
                            "drop_key": dkey,
                        }
                    )
                elif oid in unrouted_ids:
                    items.append(
                        {
                            "vehicle_id": load.vehicle_id,
                            "vehicle_code": "UNROUTED",
                            "order_id": oid,
                            "fill_ratio": fill_by_vehicle.get(load.vehicle_id),
                            "sequence": None,
                            "drop_key": None,
                        }
                    )

        routes_payload = [
            {
                "vehicle_id": r.vehicle_id,
                "vehicle_code": r.vehicle_code,
                "drop_count": r.drop_count,
                "distance_km": r.distance_km,
                "cost_eur": r.cost_eur,
                "route_status": "proposed",
            }
            for r in routing.routes
        ]
        total_km = sum(r.distance_km for r in routing.routes)
        total_cost = sum(r.cost_eur for r in routing.routes)

        meta: dict[int, tuple[str, float]] = {
            o.id: (o.delivery_code, o.weight_kg) for o in solver_orders
        }
        for order in orders:
            if order.id is not None and order.id not in meta:
                meta[order.id] = (order.delivery_code, order.total_weight_kg or 0.0)

        unassigned_set = set(unassigned_ids)
        unrouted_only = [oid for oid in unrouted_ids if oid not in unassigned_set]
        persist_unassigned = [oid for oid in unassigned_ids if oid not in unrouted_ids]

        run_id = repo.append_proposed_plan(
            run.id,
            status=plan.status,
            wall_time_s=plan.wall_time_s,
            warnings=list(plan.warnings),
            items=items,
            routes=routes_payload,
            unassigned_order_ids=persist_unassigned,
            order_meta=meta,
            total_distance_km=total_km,
            total_cost_eur=total_cost,
        )

        planned_ids = sorted(routed_ids)
        if planned_ids:
            order_repo.set_status_many(planned_ids, OrderStatus.PLANNED)

        AuditLogRepository(self._session).record(
            username=username,
            action="planning.plan",
            details={
                "run_id": run_id,
                "status": plan.status,
                "routed": len(planned_ids),
                "unrouted": len(unrouted_only),
                "unassigned": len(persist_unassigned),
                "total_distance_km": round(total_km, 2),
                "total_cost_eur": round(total_cost, 2),
                "wall_time_s": round(plan.wall_time_s, 3),
                "available_vehicles": len(vehicles),
            },
        )
        return PlanOutcome(
            plan=plan,
            run_id=run_id,
            skipped_no_weight=tuple(skipped_weight),
            skipped_no_coords=tuple(skipped_coord_codes),
            planned_order_ids=tuple(planned_ids),
        )

    def approve_route(
        self, *, run_id: int, vehicle_id: int, username: str
    ) -> ApproveOutcome:
        repo = AssignmentRepository(self._session)
        vehicle_repo = VehicleRepository(self._session)
        order_repo = OrderRepository(self._session)

        route = repo.approve_route(run_id, vehicle_id, username=username)
        order_ids = repo.list_order_ids_for_vehicle(run_id, vehicle_id)
        approved: list[int] = []
        for oid in order_ids:
            order = order_repo.get_by_id(oid)
            if order is not None and order.status == OrderStatus.PLANNED:
                approved.append(oid)
        if approved:
            order_repo.set_status_many(approved, OrderStatus.APPROVED)
        if route.vehicle_id is not None:
            vehicle_repo.set_busy(route.vehicle_id, busy=True)

        AuditLogRepository(self._session).record(
            username=username,
            action="planning.approve_route",
            details={
                "run_id": run_id,
                "vehicle_id": vehicle_id,
                "vehicle_code": route.vehicle_code,
                "approved_orders": len(approved),
                "order_ids": approved[:50],
            },
        )
        return ApproveOutcome(
            run_id=run_id,
            approved_order_ids=tuple(approved),
            vehicle_id=vehicle_id,
            vehicle_code=route.vehicle_code,
        )

    def unlock_route(
        self, *, run_id: int, vehicle_id: int, username: str
    ) -> UnlockOutcome:
        repo = AssignmentRepository(self._session)
        vehicle_repo = VehicleRepository(self._session)
        order_repo = OrderRepository(self._session)

        route = repo.unlock_route(run_id, vehicle_id)
        order_ids = repo.list_order_ids_for_vehicle(run_id, vehicle_id)
        reset: list[int] = []
        for oid in order_ids:
            order = order_repo.get_by_id(oid)
            if order is not None and order.status in {
                OrderStatus.PLANNED,
                OrderStatus.APPROVED,
            }:
                reset.append(oid)
        if reset:
            order_repo.set_status_many(reset, OrderStatus.NEW)
        if route.vehicle_id is not None:
            vehicle_repo.set_busy(route.vehicle_id, busy=False)

        AuditLogRepository(self._session).record(
            username=username,
            action="planning.unlock_route",
            details={
                "run_id": run_id,
                "vehicle_id": vehicle_id,
                "vehicle_code": route.vehicle_code,
                "reset_orders": len(reset),
            },
        )
        return UnlockOutcome(
            run_id=run_id,
            reset_order_ids=tuple(reset),
            vehicle_id=vehicle_id,
            vehicle_code=route.vehicle_code,
        )

    def approve_plan(self, *, run_id: int, username: str) -> ApproveOutcome:
        """Approve all remaining proposed routes (shortcut)."""
        repo = AssignmentRepository(self._session)
        run = repo.get_run(run_id)
        if run is None:
            raise ValueError(f"Plan run #{run_id} nie istnieje.")

        proposed = [
            r
            for r in repo.list_routes_for_run(run_id)
            if (r.route_status or "proposed") != "approved" and r.vehicle_id is not None
        ]
        if not proposed:
            raise ValueError(f"Plan #{run_id} jest już zatwierdzony — brak tras do zatwierdzenia.")

        approved_all: list[int] = []
        last_code: str | None = None
        last_vid: int | None = None
        for route in proposed:
            assert route.vehicle_id is not None
            outcome = self.approve_route(
                run_id=run_id, vehicle_id=route.vehicle_id, username=username
            )
            approved_all.extend(outcome.approved_order_ids)
            last_code = outcome.vehicle_code
            last_vid = outcome.vehicle_id
        return ApproveOutcome(
            run_id=run_id,
            approved_order_ids=tuple(approved_all),
            vehicle_id=last_vid,
            vehicle_code=last_code,
        )

    def _routed_order_ids(self, run_id: int) -> list[int]:
        items = AssignmentRepository(self._session).list_items_for_run(run_id)
        return [
            item.order_id
            for item in items
            if item.sequence is not None and item.vehicle_code not in {"UNASSIGNED", "UNROUTED"}
        ]

    def _reset_routed_orders_to_new(self, run_id: int) -> list[int]:
        order_repo = OrderRepository(self._session)
        reset: list[int] = []
        for oid in self._routed_order_ids(run_id):
            order = order_repo.get_by_id(oid)
            if order is None:
                continue
            if order.status in {OrderStatus.PLANNED, OrderStatus.APPROVED}:
                reset.append(oid)
        if reset:
            order_repo.set_status_many(reset, OrderStatus.NEW)
        return reset

    def unlock_plan(self, *, run_id: int, username: str) -> UnlockOutcome:
        """Full reset: all routes → proposed, orders → NEW, clear vehicle busy."""
        repo = AssignmentRepository(self._session)
        vehicle_repo = VehicleRepository(self._session)
        run = repo.get_run(run_id)
        if run is None:
            raise ValueError(f"Plan run #{run_id} nie istnieje.")

        for route in repo.list_routes_for_run(run_id):
            route.route_status = "proposed"
            route.approved_at = None
            route.approved_by = None
            if route.vehicle_id is not None:
                vehicle_repo.set_busy(route.vehicle_id, busy=False)
        reset = self._reset_routed_orders_to_new(run_id)
        repo.set_run_status(run_id, plan_status="draft")
        AuditLogRepository(self._session).record(
            username=username,
            action="planning.unlock",
            details={"run_id": run_id, "reset_orders": len(reset), "order_ids": reset[:50]},
        )
        return UnlockOutcome(run_id=run_id, reset_order_ids=tuple(reset))

    def delete_plan(self, *, run_id: int, username: str) -> DeletePlanOutcome:
        repo = AssignmentRepository(self._session)
        vehicle_repo = VehicleRepository(self._session)
        run = repo.get_run(run_id)
        if run is None:
            raise ValueError(f"Plan run #{run_id} nie istnieje.")

        for route in repo.list_routes_for_run(run_id):
            if route.vehicle_id is not None:
                vehicle_repo.set_busy(route.vehicle_id, busy=False)
        reset = self._reset_routed_orders_to_new(run_id)
        repo.delete_run(run_id)
        AuditLogRepository(self._session).record(
            username=username,
            action="planning.delete",
            details={"run_id": run_id, "reset_orders": len(reset), "order_ids": reset[:50]},
        )
        return DeletePlanOutcome(run_id=run_id, reset_order_ids=tuple(reset))
