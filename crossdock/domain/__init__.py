"""Domain layer: business models and invariants.

Pure business logic — no I/O, no framework imports. Enforces invariants
such as shipment inseparability (FR-019) and the default delivery
deadline (FR-024). May be imported by any other layer; imports nothing
from them.
"""
