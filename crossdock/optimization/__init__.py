"""Optimization layer: pure solver core (CP-SAT assignment + routing).

Must stay free of any I/O imports (ui, storage, ingest, httpx, pandas).
Solver input/output are plain serializable dataclasses so they can be
pickled across process boundaries (run.cpu_bound).
"""

from crossdock.optimization.assignment import solve_assignment
from crossdock.optimization.dto import (
    AssignmentRequest,
    AssignmentResult,
    PlanResult,
    RoutingRequest,
    RoutingResult,
)
from crossdock.optimization.routing import solve_routes

__all__ = [
    "AssignmentRequest",
    "AssignmentResult",
    "PlanResult",
    "RoutingRequest",
    "RoutingResult",
    "solve_assignment",
    "solve_routes",
]
