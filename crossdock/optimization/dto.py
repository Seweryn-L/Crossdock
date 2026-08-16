"""Pickle-safe DTOs for assignment and routing solvers (no ORM / I/O types)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class SolverOrder:
    """One transport order as seen by the solver (FR-019 atomic unit)."""

    id: int
    delivery_code: str
    weight_kg: float
    drop_key: str | None = None
    delivery_date: date | None = None
    must_ship: bool = False
    overdue: bool = False


@dataclass(frozen=True)
class SolverVehicle:
    """One fleet vehicle with kilogram capacity."""

    id: int
    code: str
    weight_capacity_kg: float


@dataclass(frozen=True)
class AssignmentRequest:
    """Input to the CP-SAT assignment solver."""

    orders: tuple[SolverOrder, ...]
    vehicles: tuple[SolverVehicle, ...]
    time_limit_s: float = 45.0
    seed: int = 42
    max_drops_per_route: int = 0
    planning_date: date | None = None
    ship_lead_days: int = 2


@dataclass(frozen=True)
class VehicleLoad:
    """Orders assigned to one vehicle plus fill metrics."""

    vehicle_id: int
    vehicle_code: str
    order_ids: tuple[int, ...]
    total_weight_kg: float
    capacity_kg: float

    @property
    def fill_ratio(self) -> float:
        if self.capacity_kg <= 0:
            return 0.0
        return self.total_weight_kg / self.capacity_kg


@dataclass(frozen=True)
class AssignmentResult:
    """Output of the assignment solver."""

    loads: tuple[VehicleLoad, ...]
    unassigned_order_ids: tuple[int, ...]
    status: str
    wall_time_s: float
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def assigned_order_ids(self) -> tuple[int, ...]:
        ids: list[int] = []
        for load in self.loads:
            ids.extend(load.order_ids)
        return tuple(ids)


@dataclass(frozen=True)
class VehicleRoutingInput:
    """One vehicle with drop nodes already grouped (matrix index 0 = depot)."""

    vehicle_id: int
    vehicle_code: str
    drop_keys: tuple[str, ...]
    order_ids_per_drop: tuple[tuple[int, ...], ...]
    drop_weights_kg: tuple[float, ...]
    # Square matrix in metres; size = 1 + len(drop_keys).
    distance_matrix_m: tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class RoutingRequest:
    """Input to the per-vehicle routing solver (T4)."""

    vehicles: tuple[VehicleRoutingInput, ...]
    max_drops_per_route: int = 3
    time_limit_s: float = 30.0
    seed: int = 42
    cost_per_km: float = 1.2


@dataclass(frozen=True)
class VehicleRoute:
    """Routed sequence for one vehicle."""

    vehicle_id: int
    vehicle_code: str
    ordered_order_ids: tuple[int, ...]
    ordered_drop_keys: tuple[str, ...]
    drop_count: int
    distance_km: float
    cost_eur: float


@dataclass(frozen=True)
class RoutingResult:
    """Output of the routing solver."""

    routes: tuple[VehicleRoute, ...]
    unrouted_order_ids: tuple[int, ...]
    status: str
    wall_time_s: float
    warnings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PlanResult:
    """Combined assignment + routing outcome for one plan generation."""

    assignment: AssignmentResult
    routing: RoutingResult

    @property
    def status(self) -> str:
        return f"{self.assignment.status}+{self.routing.status}"

    @property
    def wall_time_s(self) -> float:
        return self.assignment.wall_time_s + self.routing.wall_time_s

    @property
    def warnings(self) -> tuple[str, ...]:
        return tuple(self.assignment.warnings) + tuple(self.routing.warnings)


@dataclass(frozen=True)
class BufferCandidate:
    """One order evaluated by the FR-022 buffering heuristic."""

    order_id: int
    delivery_code: str
    weight_kg: float
    pallet_count: int
    distance_km: float
    slack_days: int | None = None


@dataclass(frozen=True)
class BufferRates:
    """Cost parameters for FR-022 (placeholders until W-06)."""

    cost_per_km: float
    storage_cost_per_pallet_day: float
    ltl_cost_multiplier: float
    savings_threshold: float
    max_buffer_days: int


@dataclass(frozen=True)
class BufferDecision:
    """Outcome of ship-now vs buffer for one order."""

    order_id: int
    delivery_code: str
    action: str  # "ship_now" | "buffer"
    buffer_days: int
    cost_ship_now_eur: float
    cost_buffer_eur: float
    savings_ratio: float
    pallet_count: int
    weight_kg: float
    distance_km: float
