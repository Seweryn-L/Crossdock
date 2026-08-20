"""Planning use cases: assignment + routing + plan approval."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from crossdock.config import Settings, effective_planning_date, get_settings
from crossdock.distance.factory import get_distance_provider
from crossdock.distance.haversine import HaversineDistanceProvider
from crossdock.distance.ports import DistanceProvider
from crossdock.domain.models import Location, Order, OrderStatus, Vehicle
from crossdock.domain.sla import is_overdue, slack_days
from crossdock.optimization.assignment import solve_assignment
from crossdock.optimization.dto import (
    AssignmentRequest,
    AssignmentResult,
    PlanResult,
    RoutingRequest,
    RoutingResult,
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
    WarehouseQueueRepository,
)
from crossdock.storage.tables import AssignmentRunRow
from crossdock.text_pl import PLAN_NAME_MAX_LEN, format_plan_label


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
class CompleteRouteOutcome:
    run_id: int
    delivered_order_ids: tuple[int, ...]
    vehicle_id: int
    vehicle_code: str


@dataclass(frozen=True)
class DeletePlanOutcome:
    run_id: int
    reset_order_ids: tuple[int, ...]


@dataclass(frozen=True)
class PlanListItem:
    run_id: int
    display_name: str | None
    plan_status: str
    created_at: datetime | None
    label: str


@dataclass(frozen=True)
class OrderGeoSnapshot:
    """Pickle-safe delivery coords for routing (no ORM)."""

    id: int
    delivery_code: str
    weight_kg: float
    latitude: float | None
    longitude: float | None
    drop_key: str | None


@dataclass(frozen=True)
class PlanSolveRequest:
    """Pickle-safe snapshot for run.cpu_bound assignment + routing."""

    solver_orders: tuple[SolverOrder, ...]
    solver_vehicles: tuple[SolverVehicle, ...]
    order_geos: tuple[OrderGeoSnapshot, ...]
    held_skipped: tuple[str, ...]
    skipped_weight: tuple[str, ...]
    existing_run_id: int | None
    assignment_limit_s: float
    routing_limit_s: float
    seed: int
    max_drops_per_route: int
    depot: tuple[float, float]
    cost_per_km: float
    planning_date: date | None = None
    ship_lead_days: int = 2
    extra_warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class PreparedPlanResult:
    """Pickle-safe solver output ready to persist on the UI process."""

    existing_run_id: int | None
    plan: PlanResult
    items: tuple[dict[str, Any], ...]
    routes: tuple[dict[str, Any], ...]
    unassigned_order_ids: tuple[int, ...]
    order_meta: tuple[tuple[int, str, float], ...]
    planned_order_ids: tuple[int, ...]
    skipped_no_weight: tuple[str, ...]
    skipped_no_coords: tuple[str, ...]


@dataclass(frozen=True)
class AssignmentStageResult:
    """CP-SAT assignment only — safe for ``run.cpu_bound`` (no I/O)."""

    assignment: AssignmentResult


@dataclass(frozen=True)
class RoutingBundle:
    """Pickle-safe routing inputs after distance matrix is known."""

    vehicles: tuple[VehicleRoutingInput, ...]
    skipped_coord_codes: tuple[str, ...]
    no_coords_ids: tuple[int, ...]
    # drop_key -> (lat, lon) for geometry enrichment after routing.
    drop_coords: tuple[tuple[str, float, float], ...]


def orders_to_solver(
    orders: list[Order],
    *,
    planning_date: date | None = None,
    ship_lead_days: int = 2,
    must_ship_ids: set[int] | None = None,
) -> tuple[list[SolverOrder], list[str]]:
    """Map domain orders to solver DTOs; skip those without total weight."""
    forced = must_ship_ids or set()
    solver_orders: list[SolverOrder] = []
    skipped: list[str] = []
    for order in orders:
        if order.id is None:
            continue
        weight = order.total_weight_kg
        if weight is None:
            skipped.append(order.delivery_code)
            continue
        slack = None
        if planning_date is not None:
            slack = slack_days(order.delivery_date, planning_date, ship_lead_days)
        must = order.id in forced or (slack is not None and slack <= 0)
        solver_orders.append(
            SolverOrder(
                id=order.id,
                delivery_code=order.delivery_code,
                weight_kg=weight,
                drop_key=drop_key_for_location(order.delivery_location),
                delivery_date=order.delivery_date,
                must_ship=must,
                overdue=bool(slack is not None and is_overdue(slack)),
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


def drop_key_for_location(location: Location) -> str | None:
    if location.latitude is not None and location.longitude is not None:
        return f"{location.latitude:.4f}|{location.longitude:.4f}"
    city = (location.city or "").strip()
    country = (location.country or "").strip()
    name = (location.name or "").strip()
    if city or country or name:
        return f"{city}|{country}|{name}"
    return None


def _order_to_geo(order: Order) -> OrderGeoSnapshot | None:
    if order.id is None:
        return None
    loc = order.delivery_location
    return OrderGeoSnapshot(
        id=order.id,
        delivery_code=order.delivery_code,
        weight_kg=order.total_weight_kg or 0.0,
        latitude=loc.latitude,
        longitude=loc.longitude,
        drop_key=drop_key_for_location(loc),
    )


def _build_routing_inputs(
    *,
    loads: list[Any],
    orders_by_id: dict[int, OrderGeoSnapshot],
    depot: tuple[float, float],
    distance: DistanceProvider,
) -> tuple[list[VehicleRoutingInput], list[str], set[int], dict[str, tuple[float, float]]]:
    """Group assigned orders into drop nodes; skip orders without usable coords."""
    skipped_codes: list[str] = []
    no_coords_ids: set[int] = set()
    vehicles_out: list[VehicleRoutingInput] = []
    drop_coords: dict[str, tuple[float, float]] = {}

    for load in loads:
        if not load.order_ids:
            continue
        # drop_key -> (lat, lon, order_ids, weight)
        drops: dict[str, tuple[float, float, list[int], float]] = {}
        for oid in load.order_ids:
            snap = orders_by_id.get(oid)
            if snap is None:
                continue
            if snap.latitude is None or snap.longitude is None:
                skipped_codes.append(snap.delivery_code)
                no_coords_ids.add(oid)
                continue
            key = snap.drop_key
            if key is None:
                skipped_codes.append(snap.delivery_code)
                no_coords_ids.add(oid)
                continue
            weight = snap.weight_kg
            if key not in drops:
                drops[key] = (snap.latitude, snap.longitude, [oid], weight)
            else:
                lat, lon, ids, w = drops[key]
                ids.append(oid)
                drops[key] = (lat, lon, ids, w + weight)

        if not drops:
            continue

        keys = list(drops.keys())
        for key in keys:
            drop_coords[key] = (drops[key][0], drops[key][1])
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
    return vehicles_out, skipped_codes, no_coords_ids, drop_coords


def solve_assignment_stage(request: PlanSolveRequest) -> AssignmentStageResult:
    """CP-SAT only — safe for ``run.cpu_bound`` (no distance I/O)."""
    assignment = solve_assignment(
        AssignmentRequest(
            orders=request.solver_orders,
            vehicles=request.solver_vehicles,
            time_limit_s=request.assignment_limit_s,
            seed=request.seed,
            max_drops_per_route=request.max_drops_per_route,
            planning_date=request.planning_date,
            ship_lead_days=request.ship_lead_days,
        )
    )
    return AssignmentStageResult(assignment=assignment)


def build_routing_bundle(
    assignment: AssignmentResult,
    request: PlanSolveRequest,
    *,
    distance: DistanceProvider | None = None,
) -> RoutingBundle:
    """Build per-vehicle matrices. May call OSRM — use ``run.io_bound``."""
    provider = distance if distance is not None else HaversineDistanceProvider()
    geos_by_id = {g.id: g for g in request.order_geos}
    routing_inputs, skipped_coord_codes, no_coords_ids, drop_coords = _build_routing_inputs(
        loads=list(assignment.loads),
        orders_by_id=geos_by_id,
        depot=request.depot,
        distance=provider,
    )
    return RoutingBundle(
        vehicles=tuple(routing_inputs),
        skipped_coord_codes=tuple(skipped_coord_codes),
        no_coords_ids=tuple(sorted(no_coords_ids)),
        drop_coords=tuple((k, lat, lon) for k, (lat, lon) in drop_coords.items()),
    )


def solve_routes_stage(
    request: PlanSolveRequest,
    bundle: RoutingBundle,
) -> RoutingResult:
    """OR-Tools routing on a prepared matrix — safe for ``run.cpu_bound``."""
    return solve_routes(
        RoutingRequest(
            vehicles=bundle.vehicles,
            max_drops_per_route=request.max_drops_per_route,
            time_limit_s=request.routing_limit_s,
            seed=request.seed,
            cost_per_km=request.cost_per_km,
        )
    )


def assemble_prepared_plan(
    request: PlanSolveRequest,
    assignment: AssignmentResult,
    bundle: RoutingBundle,
    routing: RoutingResult,
    *,
    polylines_by_vehicle: dict[int, list[tuple[float, float]]] | None = None,
) -> PreparedPlanResult:
    """Map solver output to persistable DTOs (pure CPU)."""
    warnings = list(assignment.warnings) + list(routing.warnings)
    if request.held_skipped:
        held = request.held_skipped
        warnings.append(
            f"Wstrzymane w magazynie: {len(held)} zleceń (poza planem)"
            + (": " + ", ".join(held[:10]) if held else "")
            + ("…" if len(held) > 10 else "")
        )
    if request.skipped_weight:
        skipped_weight = request.skipped_weight
        warnings.append(
            f"Pominięto {len(skipped_weight)} zleceń bez wagi (kg): "
            + ", ".join(skipped_weight[:10])
            + ("…" if len(skipped_weight) > 10 else "")
        )
    skipped_coord_codes = list(bundle.skipped_coord_codes)
    if skipped_coord_codes:
        warnings.append(
            f"Brak współrzędnych dla {len(skipped_coord_codes)} zleceń "
            f"(bez trasy): "
            + ", ".join(skipped_coord_codes[:10])
            + ("…" if len(skipped_coord_codes) > 10 else "")
        )
    warnings.extend(request.extra_warnings)

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
    routing_inputs = list(bundle.vehicles)
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
    no_coords_ids = set(bundle.no_coords_ids)
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

    poly = polylines_by_vehicle or {}
    routes_payload = [
        {
            "vehicle_id": r.vehicle_id,
            "vehicle_code": r.vehicle_code,
            "drop_count": r.drop_count,
            "distance_km": r.distance_km,
            "cost_eur": r.cost_eur,
            "polyline": poly.get(r.vehicle_id),
        }
        for r in routing.routes
    ]

    meta_map: dict[int, tuple[str, float]] = {
        o.id: (o.delivery_code, o.weight_kg) for o in request.solver_orders
    }
    for geo in request.order_geos:
        if geo.id not in meta_map:
            meta_map[geo.id] = (geo.delivery_code, geo.weight_kg)

    persist_unassigned = [oid for oid in unassigned_ids if oid not in unrouted_ids]
    planned_ids = tuple(sorted(routed_ids))
    return PreparedPlanResult(
        existing_run_id=request.existing_run_id,
        plan=plan,
        items=tuple(items),
        routes=tuple(routes_payload),
        unassigned_order_ids=tuple(persist_unassigned),
        order_meta=tuple((oid, code, weight) for oid, (code, weight) in meta_map.items()),
        planned_order_ids=planned_ids,
        skipped_no_weight=request.skipped_weight,
        skipped_no_coords=tuple(skipped_coord_codes),
    )


def waypoints_for_route(
    *,
    depot: tuple[float, float],
    ordered_drop_keys: tuple[str, ...],
    drop_coords: dict[str, tuple[float, float]],
) -> list[tuple[float, float]]:
    """Closed path depot → drops in sequence → depot."""
    path: list[tuple[float, float]] = [depot]
    for key in ordered_drop_keys:
        coords = drop_coords.get(key)
        if coords is None:
            continue
        path.append(coords)
    path.append(depot)
    return path


def fetch_route_polylines(
    routing: RoutingResult,
    request: PlanSolveRequest,
    bundle: RoutingBundle,
    *,
    route_fetcher: Any,
) -> dict[int, list[tuple[float, float]]]:
    """Call OSRM ``/route`` (or any fetcher) per vehicle. Use ``run.io_bound``."""
    drop_coords = {key: (lat, lon) for key, lat, lon in bundle.drop_coords}
    out: dict[int, list[tuple[float, float]]] = {}
    for route in routing.routes:
        points = waypoints_for_route(
            depot=request.depot,
            ordered_drop_keys=route.ordered_drop_keys,
            drop_coords=drop_coords,
        )
        if len(points) < 2:
            continue
        try:
            out[route.vehicle_id] = list(route_fetcher(points))
        except Exception:
            # Fallback: straight segments between waypoints.
            out[route.vehicle_id] = points
    return out


def with_route_polylines(
    prepared: PreparedPlanResult,
    polylines_by_vehicle: dict[int, list[tuple[float, float]]],
) -> PreparedPlanResult:
    """Attach road geometries to an already-assembled plan result."""
    routes = []
    for route in prepared.routes:
        payload = dict(route)
        vid = payload.get("vehicle_id")
        if isinstance(vid, int) and vid in polylines_by_vehicle:
            payload["polyline"] = polylines_by_vehicle[vid]
        routes.append(payload)
    return PreparedPlanResult(
        existing_run_id=prepared.existing_run_id,
        plan=prepared.plan,
        items=prepared.items,
        routes=tuple(routes),
        unassigned_order_ids=prepared.unassigned_order_ids,
        order_meta=prepared.order_meta,
        planned_order_ids=prepared.planned_order_ids,
        skipped_no_weight=prepared.skipped_no_weight,
        skipped_no_coords=prepared.skipped_no_coords,
    )


def solve_prepared_plan(
    request: PlanSolveRequest,
    *,
    distance: DistanceProvider | None = None,
    route_fetcher: Any | None = None,
) -> PreparedPlanResult:
    """Assignment + routing. Prefer the staged UI path when OSRM I/O is enabled.

    Sync helper for tests and ``PlanningService.run_plan``. When ``distance``
    performs HTTP (OSRM), this must not be called from ``run.cpu_bound``.
    """
    stage = solve_assignment_stage(request)
    bundle = build_routing_bundle(stage.assignment, request, distance=distance)
    routing = solve_routes_stage(request, bundle)
    polylines: dict[int, list[tuple[float, float]]] | None = None
    if route_fetcher is not None:
        polylines = fetch_route_polylines(routing, request, bundle, route_fetcher=route_fetcher)
    return assemble_prepared_plan(
        request,
        stage.assignment,
        bundle,
        routing,
        polylines_by_vehicle=polylines,
    )


class PlanningService:
    def __init__(self, session: Session, *, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()

    def _exclude_held(self, orders: list[Order]) -> tuple[list[Order], list[str]]:
        held = WarehouseQueueRepository(self._session).held_order_ids()
        if not held:
            return orders, []
        kept: list[Order] = []
        skipped: list[str] = []
        for order in orders:
            if order.id is not None and order.id in held:
                skipped.append(order.delivery_code)
            else:
                kept.append(order)
        return kept, skipped

    def _must_ship_ids(self, orders: list[Order]) -> set[int]:
        planning = effective_planning_date(self._settings)
        lead = self._settings.ship_lead_days
        forced: set[int] = set()
        queued = WarehouseQueueRepository(self._session).list_ordered()
        if queued:
            top = queued[0]
            if top.status != "held":
                forced.add(top.order_id)
        for order in orders:
            if order.id is None:
                continue
            if slack_days(order.delivery_date, planning, lead) <= 0:
                forced.add(order.id)
        capacity = float(self._settings.warehouse_capacity_kg)
        if capacity > 0:
            weights = {o.id: (o.total_weight_kg or 0.0) for o in orders if o.id is not None}
            total = sum(weights.values())
            excess = total - capacity
            if excess > 0:
                must_kg = sum(weights.get(oid, 0.0) for oid in forced)
                need = excess - must_kg
                if need > 0:
                    optionals = [o for o in orders if o.id is not None and o.id not in forced]
                    optionals.sort(
                        key=lambda o: (
                            slack_days(o.delivery_date, planning, lead),
                            -(o.total_weight_kg or 0.0),
                        )
                    )
                    acc = 0.0
                    for order in optionals:
                        assert order.id is not None
                        forced.add(order.id)
                        acc += weights.get(order.id, 0.0)
                        if acc >= need:
                            break
        return forced

    def _stock_overflow_warning(self, orders: list[Order]) -> str | None:
        capacity = float(self._settings.warehouse_capacity_kg)
        if capacity <= 0:
            return None
        total = sum(float(o.total_weight_kg or 0.0) for o in orders)
        if total <= capacity:
            return None
        return (
            f"Magazyn ponad pojemność ({total:.0f} / {capacity:.0f} kg) — "
            "wypycham najpilniejsze zlecenia."
        )

    def run_assignment(self, *, username: str) -> PlanningOutcome:
        orders, held_skipped = self._exclude_held(
            OrderRepository(self._session).list_by_status(OrderStatus.NEW)
        )
        vehicles = VehicleRepository(self._session).list_active()
        must_ids = self._must_ship_ids(orders)
        solver_orders, skipped = orders_to_solver(
            orders,
            planning_date=effective_planning_date(self._settings),
            ship_lead_days=self._settings.ship_lead_days,
            must_ship_ids=must_ids,
        )
        solver_vehicles = vehicles_to_solver(vehicles)

        request = AssignmentRequest(
            orders=tuple(solver_orders),
            vehicles=tuple(solver_vehicles),
            time_limit_s=self._settings.solver_time_limit_s,
            seed=self._settings.solver_seed,
            max_drops_per_route=self._settings.max_drops_per_route,
            planning_date=effective_planning_date(self._settings),
            ship_lead_days=self._settings.ship_lead_days,
        )
        result = solve_assignment(request)

        warnings = list(result.warnings)
        if held_skipped:
            warnings.append(
                f"Wstrzymane w magazynie: {len(held_skipped)} zleceń (poza planem)"
                + (": " + ", ".join(held_skipped[:10]) if held_skipped else "")
                + ("…" if len(held_skipped) > 10 else "")
            )
        if skipped:
            warnings.append(
                f"Pominięto {len(skipped)} zleceń bez wagi (kg): "
                + ", ".join(skipped[:10])
                + ("…" if len(skipped) > 10 else "")
            )
        overflow = self._stock_overflow_warning(orders)
        if overflow:
            warnings.append(overflow)
        if warnings != list(result.warnings):
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

    def prepare_plan_request(
        self,
        *,
        target_run_id: int | None = None,
        force_new: bool = False,
    ) -> PlanSolveRequest:
        """Read-only snapshot of solver input. Does not delete or mutate rows.

        Appends to ``target_run_id`` when that run is a draft/partial.
        An approved target, a missing target, or ``force_new`` starts a new run
        (does not rewrite another plan's approved routes).
        """
        repo = AssignmentRepository(self._session)
        vehicle_repo = VehicleRepository(self._session)
        order_repo = OrderRepository(self._session)
        target = None if force_new else self._run_for_append(target_run_id)

        vehicles = vehicle_repo.list_available()
        if not vehicles:
            raise ValueError("Brak wolnych pojazdów — odblokuj trasę albo dodaj flotę.")

        extra: list[Order] = []
        existing_run_id: int | None = None
        if target is not None and target.plan_status == "draft":
            existing_run_id = target.id
            extra = self._planned_orders_on_run(target.id)
        elif target is not None and target.plan_status == "partial":
            existing_run_id = target.id
            approved_vehicle_ids = {
                r.vehicle_id
                for r in repo.list_routes_for_run(target.id)
                if r.route_status == "approved" and r.vehicle_id is not None
            }
            for item in repo.list_items_for_run(target.id):
                keep = item.vehicle_id in approved_vehicle_ids and item.vehicle_code not in {
                    "UNASSIGNED",
                    "UNROUTED",
                }
                if keep:
                    continue
                order = order_repo.get_by_id(item.order_id)
                if order is not None and order.status == OrderStatus.PLANNED:
                    extra.append(order)

        by_id: dict[int, Order] = {}
        for order in order_repo.list_by_status(OrderStatus.NEW):
            if order.id is not None:
                by_id[order.id] = order
        for order in extra:
            if order.id is not None:
                by_id[order.id] = order
        orders, held_skipped = self._exclude_held(list(by_id.values()))
        planning = effective_planning_date(self._settings)
        must_ids = self._must_ship_ids(orders)
        solver_orders, skipped_weight = orders_to_solver(
            orders,
            planning_date=planning,
            ship_lead_days=self._settings.ship_lead_days,
            must_ship_ids=must_ids,
        )
        geos: list[OrderGeoSnapshot] = []
        for order in orders:
            geo = _order_to_geo(order)
            if geo is not None:
                geos.append(geo)

        total_limit = self._settings.solver_time_limit_s
        return PlanSolveRequest(
            solver_orders=tuple(solver_orders),
            solver_vehicles=tuple(vehicles_to_solver(vehicles)),
            order_geos=tuple(geos),
            held_skipped=tuple(held_skipped),
            skipped_weight=tuple(skipped_weight),
            existing_run_id=existing_run_id,
            assignment_limit_s=max(5.0, total_limit * 0.4),
            routing_limit_s=max(5.0, total_limit * 0.6),
            seed=self._settings.solver_seed,
            max_drops_per_route=self._settings.max_drops_per_route,
            depot=(self._settings.depot_latitude, self._settings.depot_longitude),
            cost_per_km=self._settings.cost_per_km,
            planning_date=planning,
            ship_lead_days=self._settings.ship_lead_days,
            extra_warnings=tuple(
                w for w in [self._stock_overflow_warning(orders)] if w is not None
            ),
        )

    def persist_prepared_plan(self, prepared: PreparedPlanResult, *, username: str) -> PlanOutcome:
        """Short write transaction: replace proposed payload, then save the new plan."""
        repo = AssignmentRepository(self._session)
        order_repo = OrderRepository(self._session)
        existing_run_id = prepared.existing_run_id
        if existing_run_id is not None:
            latest = repo.get_run(existing_run_id)
            if latest is not None and latest.plan_status == "approved":
                raise ValueError(
                    "Ten plan jest już zatwierdzony — wygeneruj nowy plan albo odblokuj trasy."
                )
            if latest is not None and latest.plan_status == "draft":
                prev_ids = [
                    oid
                    for oid in self._routed_order_ids(latest.id)
                    if self._order_status_is(oid, OrderStatus.PLANNED)
                ]
                if prev_ids:
                    order_repo.set_status_many(prev_ids, OrderStatus.NEW)
                repo.delete_proposed_payload(latest.id)
            elif latest is not None and latest.plan_status == "partial":
                self._reset_proposed_orders_to_new(latest.id)
                repo.delete_proposed_payload(latest.id)

        plan = prepared.plan
        meta = {oid: (code, weight) for oid, code, weight in prepared.order_meta}
        total_km = sum(float(r["distance_km"]) for r in prepared.routes)
        total_cost = sum(float(r["cost_eur"]) for r in prepared.routes)
        run_id = repo.save_plan_run(
            username=username,
            status=plan.status,
            wall_time_s=plan.wall_time_s,
            warnings=list(plan.warnings),
            items=list(prepared.items),
            routes=list(prepared.routes),
            unassigned_order_ids=list(prepared.unassigned_order_ids),
            order_meta=meta,
            total_distance_km=total_km,
            total_cost_eur=total_cost,
            existing_run_id=existing_run_id,
        )

        planned_ids = list(prepared.planned_order_ids)
        if planned_ids:
            order_repo.set_status_many(planned_ids, OrderStatus.PLANNED)

        unrouted_only = [
            item["order_id"] for item in prepared.items if item.get("vehicle_code") == "UNROUTED"
        ]
        AuditLogRepository(self._session).record(
            username=username,
            action="planning.plan",
            details={
                "run_id": run_id,
                "status": plan.status,
                "routed": len(planned_ids),
                "unrouted": len(unrouted_only),
                "unassigned": len(prepared.unassigned_order_ids),
                "total_distance_km": round(total_km, 2),
                "total_cost_eur": round(total_cost, 2),
                "wall_time_s": round(plan.wall_time_s, 3),
            },
        )
        return PlanOutcome(
            plan=plan,
            run_id=run_id,
            skipped_no_weight=prepared.skipped_no_weight,
            skipped_no_coords=prepared.skipped_no_coords,
            planned_order_ids=prepared.planned_order_ids,
        )

    def run_plan(
        self,
        *,
        username: str,
        target_run_id: int | None = None,
        force_new: bool = False,
    ) -> PlanOutcome:
        request = self.prepare_plan_request(target_run_id=target_run_id, force_new=force_new)
        distance = get_distance_provider(self._settings)
        route_fetcher = None
        if self._settings.use_osrm and hasattr(distance, "route_polyline"):
            route_fetcher = distance.route_polyline
        prepared = solve_prepared_plan(
            request,
            distance=distance,
            route_fetcher=route_fetcher,
        )
        return self.persist_prepared_plan(prepared, username=username)

    def list_recent_plans(self, *, limit: int = 30) -> tuple[PlanListItem, ...]:
        rows = AssignmentRepository(self._session).list_recent_runs(limit=limit)
        return tuple(self._to_plan_list_item(row) for row in rows)

    def resolve_run_id(self, preferred: int | None) -> int | None:
        return AssignmentRepository(self._session).resolve_run_id(preferred)

    def resolve_operational_run_id(self) -> int | None:
        return AssignmentRepository(self._session).resolve_operational_run_id()

    def create_empty_plan(self, *, username: str) -> int:
        run_id = AssignmentRepository(self._session).save_plan_run(
            username=username,
            status="empty",
            wall_time_s=0.0,
            warnings=[],
            items=[],
            routes=[],
            unassigned_order_ids=[],
            order_meta={},
            total_distance_km=None,
            total_cost_eur=None,
        )
        AuditLogRepository(self._session).record(
            username=username,
            action="planning.create",
            details={"run_id": run_id},
        )
        return run_id

    def rename_plan(self, *, run_id: int, display_name: str, username: str) -> str | None:
        name = display_name.strip()
        if len(name) > PLAN_NAME_MAX_LEN:
            raise ValueError(f"Nazwa planu może mieć maksymalnie {PLAN_NAME_MAX_LEN} znaków.")
        stored = name or None
        repo = AssignmentRepository(self._session)
        run = repo.get_run(run_id)
        if run is None:
            raise ValueError(f"Plan run #{run_id} nie istnieje.")
        previous = run.display_name
        repo.set_display_name(run_id, stored)
        AuditLogRepository(self._session).record(
            username=username,
            action="planning.rename",
            details={"run_id": run_id, "previous": previous, "display_name": stored},
        )
        return stored

    def _to_plan_list_item(self, row: AssignmentRunRow) -> PlanListItem:
        display_name = row.display_name
        created_at = row.created_at
        return PlanListItem(
            run_id=int(row.id),
            display_name=display_name,
            plan_status=str(row.plan_status),
            created_at=created_at,
            label=format_plan_label(
                run_id=int(row.id),
                display_name=display_name,
                plan_status=str(row.plan_status),
                created_at=created_at,
            ),
        )

    def _run_for_append(self, target_run_id: int | None) -> AssignmentRunRow | None:
        repo = AssignmentRepository(self._session)
        run = repo.get_run(target_run_id) if target_run_id is not None else repo.get_latest_run()
        if run is None:
            return None
        if run.plan_status in {"draft", "partial"}:
            return run
        return None

    def _planned_orders_on_run(self, run_id: int) -> list[Order]:
        extra: list[Order] = []
        order_repo = OrderRepository(self._session)
        for item in AssignmentRepository(self._session).list_items_for_run(run_id):
            if item.vehicle_code in {"UNASSIGNED", "UNROUTED"}:
                continue
            order = order_repo.get_by_id(item.order_id)
            if order is not None and order.status == OrderStatus.PLANNED:
                extra.append(order)
        return extra

    def _order_status_is(self, order_id: int, status: OrderStatus) -> bool:
        order = OrderRepository(self._session).get_by_id(order_id)
        return order is not None and order.status == status

    def approve_plan(self, *, run_id: int, username: str) -> ApproveOutcome:
        repo = AssignmentRepository(self._session)
        run = repo.get_run(run_id)
        if run is None:
            raise ValueError(f"Plan run #{run_id} nie istnieje.")
        if run.plan_status == "approved":
            raise ValueError(f"Plan run #{run_id} jest już zatwierdzony.")

        from crossdock.services.plan_view import build_plan_view

        view = build_plan_view(self._session, settings=self._settings, run_id=run_id)
        send_codes = {
            str(row["vehicle"])
            for row in view.routes
            if row.get("disposition") == "send" and row.get("route_status") != "approved"
        }
        items = repo.list_items_for_run(run_id)
        to_approve = [
            item.order_id
            for item in items
            if item.sequence is not None
            and item.vehicle_code not in {"UNASSIGNED", "UNROUTED"}
            and item.vehicle_code in send_codes
        ]
        order_repo = OrderRepository(self._session)
        approved: list[int] = []
        for oid in to_approve:
            order = order_repo.get_by_id(oid)
            if order is not None and order.status == OrderStatus.PLANNED:
                approved.append(oid)
        if not approved:
            hold_n = sum(1 for row in view.routes if row.get("disposition") == "hold")
            if hold_n:
                raise ValueError(
                    "Brak pełnych tras do zatwierdzenia — słabe auta czekają na dopełnienie."
                )
        if approved:
            order_repo.set_status_many(approved, OrderStatus.APPROVED)
        dequeued = self._dequeue_orders(approved)
        vehicle_repo = VehicleRepository(self._session)
        any_hold = False
        for route in repo.list_routes_for_run(run_id):
            if route.vehicle_code in send_codes:
                route.route_status = "approved"
                if route.vehicle_id is not None:
                    vehicle_repo.set_busy(route.vehicle_id, True)
            elif route.route_status != "approved":
                any_hold = True

        if any_hold:
            self._sync_plan_status_from_routes(run_id, username=username)
        else:
            repo.approve_run(run_id, username=username)
        AuditLogRepository(self._session).record(
            username=username,
            action="planning.approve",
            details={
                "run_id": run_id,
                "approved_orders": len(approved),
                "dequeued": dequeued,
                "order_ids": approved[:50],
            },
        )
        return ApproveOutcome(run_id=run_id, approved_order_ids=tuple(approved))

    def approve_route(self, *, run_id: int, vehicle_id: int, username: str) -> ApproveOutcome:
        repo = AssignmentRepository(self._session)
        run = repo.get_run(run_id)
        if run is None:
            raise ValueError(f"Plan run #{run_id} nie istnieje.")
        route = next(
            (r for r in repo.list_routes_for_run(run_id) if r.vehicle_id == vehicle_id),
            None,
        )
        if route is None:
            raise ValueError("Nie znaleziono trasy dla zaznaczonego pojazdu.")
        if route.route_status == "completed":
            raise ValueError(f"Trasa {route.vehicle_code} jest już zrealizowana.")
        if route.route_status == "approved":
            raise ValueError(f"Trasa {route.vehicle_code} jest już zatwierdzona.")
        items = [
            item
            for item in repo.list_items_for_run(run_id)
            if item.vehicle_id == vehicle_id
            and item.sequence is not None
            and item.vehicle_code not in {"UNASSIGNED", "UNROUTED"}
        ]
        order_repo = OrderRepository(self._session)
        approved: list[int] = []
        for item in items:
            order = order_repo.get_by_id(item.order_id)
            if order is not None and order.status == OrderStatus.PLANNED:
                approved.append(item.order_id)
        if approved:
            order_repo.set_status_many(approved, OrderStatus.APPROVED)
        dequeued = self._dequeue_orders(approved)
        route.route_status = "approved"
        VehicleRepository(self._session).set_busy(vehicle_id, True)
        self._sync_plan_status_from_routes(run_id, username=username)
        AuditLogRepository(self._session).record(
            username=username,
            action="planning.approve_route",
            details={
                "run_id": run_id,
                "vehicle_id": vehicle_id,
                "vehicle_code": route.vehicle_code,
                "approved_orders": len(approved),
                "dequeued": dequeued,
                "order_ids": approved[:50],
            },
        )
        return ApproveOutcome(
            run_id=run_id,
            approved_order_ids=tuple(approved),
            vehicle_id=vehicle_id,
            vehicle_code=route.vehicle_code,
        )

    def unlock_route(self, *, run_id: int, vehicle_id: int, username: str) -> UnlockOutcome:
        repo = AssignmentRepository(self._session)
        run = repo.get_run(run_id)
        if run is None:
            raise ValueError(f"Plan run #{run_id} nie istnieje.")
        route = next(
            (r for r in repo.list_routes_for_run(run_id) if r.vehicle_id == vehicle_id),
            None,
        )
        if route is None:
            raise ValueError("Nie znaleziono trasy dla zaznaczonego pojazdu.")
        if route.route_status == "completed":
            raise ValueError(
                f"Trasa {route.vehicle_code} jest zrealizowana — nie można jej odblokować."
            )
        if route.route_status != "approved":
            raise ValueError("Odblokować można tylko zatwierdzoną trasę.")
        order_repo = OrderRepository(self._session)
        reset: list[int] = []
        for item in repo.list_items_for_run(run_id):
            if item.vehicle_id != vehicle_id:
                continue
            if item.sequence is None or item.vehicle_code in {"UNASSIGNED", "UNROUTED"}:
                continue
            order = order_repo.get_by_id(item.order_id)
            if order is not None and order.status in {OrderStatus.PLANNED, OrderStatus.APPROVED}:
                reset.append(item.order_id)
        if reset:
            order_repo.set_status_many(reset, OrderStatus.NEW)
        route.route_status = "proposed"
        VehicleRepository(self._session).set_busy(vehicle_id, False)
        self._sync_plan_status_from_routes(run_id, username=username)
        AuditLogRepository(self._session).record(
            username=username,
            action="planning.unlock_route",
            details={
                "run_id": run_id,
                "vehicle_id": vehicle_id,
                "vehicle_code": route.vehicle_code,
                "reset_orders": len(reset),
                "order_ids": reset[:50],
            },
        )
        return UnlockOutcome(
            run_id=run_id,
            reset_order_ids=tuple(reset),
            vehicle_id=vehicle_id,
            vehicle_code=route.vehicle_code,
        )

    def complete_route(
        self, *, run_id: int, vehicle_id: int, username: str
    ) -> CompleteRouteOutcome:
        repo = AssignmentRepository(self._session)
        run = repo.get_run(run_id)
        if run is None:
            raise ValueError(f"Plan run #{run_id} nie istnieje.")
        route = next(
            (r for r in repo.list_routes_for_run(run_id) if r.vehicle_id == vehicle_id),
            None,
        )
        if route is None:
            raise ValueError("Nie znaleziono trasy dla zaznaczonego pojazdu.")
        if route.route_status == "completed":
            raise ValueError(f"Trasa {route.vehicle_code} jest już zrealizowana.")
        if route.route_status != "approved":
            raise ValueError("Zrealizować można tylko zatwierdzoną trasę.")
        order_repo = OrderRepository(self._session)
        delivered: list[int] = []
        for item in repo.list_items_for_run(run_id):
            if item.vehicle_id != vehicle_id:
                continue
            if item.sequence is None or item.vehicle_code in {"UNASSIGNED", "UNROUTED"}:
                continue
            order = order_repo.get_by_id(item.order_id)
            if order is not None and order.id is not None and order.id not in delivered:
                delivered.append(order.id)
        if delivered:
            order_repo.set_status_many(delivered, OrderStatus.DELIVERED)
        dequeued = self._dequeue_orders(delivered)
        route.route_status = "completed"
        VehicleRepository(self._session).set_busy(vehicle_id, False)
        self._sync_plan_status_from_routes(run_id, username=username)
        AuditLogRepository(self._session).record(
            username=username,
            action="planning.complete_route",
            details={
                "run_id": run_id,
                "vehicle_id": vehicle_id,
                "vehicle_code": route.vehicle_code,
                "delivered_orders": len(delivered),
                "dequeued": dequeued,
                "order_ids": delivered[:50],
            },
        )
        return CompleteRouteOutcome(
            run_id=run_id,
            delivered_order_ids=tuple(delivered),
            vehicle_id=vehicle_id,
            vehicle_code=route.vehicle_code,
        )

    def _dequeue_orders(self, order_ids: list[int]) -> int:
        queue = WarehouseQueueRepository(self._session)
        dequeued = 0
        for oid in order_ids:
            if queue.delete_by_order_id(oid):
                dequeued += 1
        return dequeued

    def _reset_proposed_orders_to_new(self, run_id: int) -> list[int]:
        repo = AssignmentRepository(self._session)
        approved_vehicle_ids = {
            r.vehicle_id
            for r in repo.list_routes_for_run(run_id)
            if r.route_status in {"approved", "completed"} and r.vehicle_id is not None
        }
        order_repo = OrderRepository(self._session)
        reset: list[int] = []
        for item in repo.list_items_for_run(run_id):
            keep = item.vehicle_id in approved_vehicle_ids and item.vehicle_code not in {
                "UNASSIGNED",
                "UNROUTED",
            }
            if keep:
                continue
            order = order_repo.get_by_id(item.order_id)
            if order is not None and order.status == OrderStatus.PLANNED:
                reset.append(item.order_id)
        if reset:
            order_repo.set_status_many(reset, OrderStatus.NEW)
        return reset

    def _sync_plan_status_from_routes(self, run_id: int, *, username: str) -> None:
        repo = AssignmentRepository(self._session)
        routes = repo.list_routes_for_run(run_id)
        if not routes:
            repo.set_run_status(run_id, plan_status="draft")
            return
        statuses = {r.route_status for r in routes}
        closed = {"approved", "completed"}
        if statuses <= closed:
            run = repo.get_run(run_id)
            if run is not None and run.plan_status != "approved":
                repo.approve_run(run_id, username=username)
        elif "approved" in statuses or "completed" in statuses:
            repo.set_run_status(run_id, plan_status="partial")
        else:
            repo.set_run_status(run_id, plan_status="draft")

    def _clear_busy_for_run(self, run_id: int) -> None:
        repo = AssignmentRepository(self._session)
        vehicle_repo = VehicleRepository(self._session)
        for route in repo.list_routes_for_run(run_id):
            if route.vehicle_id is not None:
                vehicle_repo.set_busy(route.vehicle_id, False)

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
        repo = AssignmentRepository(self._session)
        run = repo.get_run(run_id)
        if run is None:
            raise ValueError(f"Plan run #{run_id} nie istnieje.")
        if run.plan_status not in {"approved", "partial"}:
            raise ValueError(
                f"Plan run #{run_id} nie jest zatwierdzony (status: {run.plan_status})."
            )

        routes = repo.list_routes_for_run(run_id)
        completed = [r for r in routes if r.route_status == "completed"]
        to_unlock = [r for r in routes if r.route_status == "approved"]
        if not to_unlock:
            if routes and all(r.route_status == "completed" for r in routes):
                raise ValueError(
                    f"Plan run #{run_id} ma tylko zrealizowane trasy — nie można odblokować."
                )
            raise ValueError(f"Plan run #{run_id} nie ma zatwierdzonych tras do odblokowania.")

        completed_vehicle_ids = {r.vehicle_id for r in completed if r.vehicle_id is not None}
        order_repo = OrderRepository(self._session)
        reset: list[int] = []
        for item in repo.list_items_for_run(run_id):
            if item.vehicle_id in completed_vehicle_ids:
                continue
            if item.sequence is None or item.vehicle_code in {"UNASSIGNED", "UNROUTED"}:
                continue
            order = order_repo.get_by_id(item.order_id)
            if order is not None and order.status in {OrderStatus.PLANNED, OrderStatus.APPROVED}:
                reset.append(item.order_id)
        if reset:
            order_repo.set_status_many(reset, OrderStatus.NEW)
        vehicle_repo = VehicleRepository(self._session)
        for route in to_unlock:
            route.route_status = "proposed"
            if route.vehicle_id is not None:
                vehicle_repo.set_busy(route.vehicle_id, False)
        self._sync_plan_status_from_routes(run_id, username=username)
        AuditLogRepository(self._session).record(
            username=username,
            action="planning.unlock",
            details={"run_id": run_id, "reset_orders": len(reset), "order_ids": reset[:50]},
        )
        return UnlockOutcome(run_id=run_id, reset_order_ids=tuple(reset))

    def delete_plan(self, *, run_id: int, username: str) -> DeletePlanOutcome:
        repo = AssignmentRepository(self._session)
        run = repo.get_run(run_id)
        if run is None:
            raise ValueError(f"Plan run #{run_id} nie istnieje.")
        if any(r.route_status == "completed" for r in repo.list_routes_for_run(run_id)):
            raise ValueError(
                f"Plan run #{run_id} ma zrealizowane trasy — nie można usunąć historii."
            )

        reset = self._reset_routed_orders_to_new(run_id)
        self._clear_busy_for_run(run_id)
        repo.delete_run(run_id)
        AuditLogRepository(self._session).record(
            username=username,
            action="planning.delete",
            details={"run_id": run_id, "reset_orders": len(reset), "order_ids": reset[:50]},
        )
        return DeletePlanOutcome(run_id=run_id, reset_order_ids=tuple(reset))
