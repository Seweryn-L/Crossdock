"""Pickle-safe DTOs for the assignment solver (no ORM / I/O types)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SolverOrder:
    """One transport order as seen by the solver (FR-019 atomic unit)."""

    id: int
    delivery_code: str
    weight_kg: float


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
