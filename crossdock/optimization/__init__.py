"""Optimization layer: pure solver core (CP-SAT + Routing, from T3).

Must stay free of any I/O imports (ui, storage, ingest, httpx, pandas).
Solver input/output are plain serializable dataclasses so they can be
pickled across process boundaries (run.cpu_bound).
"""
