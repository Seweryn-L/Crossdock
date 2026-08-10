"""Optimization layer: pure solver core (CP-SAT assignment in T3; routing in T4).

Must stay free of any I/O imports (ui, storage, ingest, httpx, pandas).
Solver input/output are plain serializable dataclasses so they can be
pickled across process boundaries (run.cpu_bound).
"""

from crossdock.optimization.assignment import solve_assignment
from crossdock.optimization.dto import AssignmentRequest, AssignmentResult

__all__ = ["AssignmentRequest", "AssignmentResult", "solve_assignment"]
