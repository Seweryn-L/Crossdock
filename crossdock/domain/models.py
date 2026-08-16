"""Core domain models and invariants.

Key invariants enforced here:

- FR-019: shipments linked to a single order are inseparable — they must
  always travel on the same vehicle / warehouse schedule. The unit of
  transport assignment is therefore always the whole order; any attempt
  to split its shipments raises ``InseparableShipmentsError``.
- FR-024: orders created without an explicit delivery date receive a
  default deadline of *today + N calendar days* (N comes from
  configuration, default 7).
"""

from __future__ import annotations

from datetime import date, timedelta
from enum import StrEnum

from pydantic import BaseModel, Field

DEFAULT_DELIVERY_DAYS = 7


class DomainError(Exception):
    """Base class for domain rule violations."""


class InseparableShipmentsError(DomainError):
    """Raised when shipments of one order would be split (FR-019)."""


class Role(StrEnum):
    ADMIN = "admin"
    DISPATCHER = "dispatcher"
    VIEWER = "viewer"


class OrderStatus(StrEnum):
    NEW = "new"
    PLANNED = "planned"
    APPROVED = "approved"
    PICKED_UP = "picked_up"
    DELIVERED = "delivered"


class VehicleType(StrEnum):
    """Fleet vehicle categories used by the company (bus / truck / curtain)."""

    BUS = "bus"
    TRUCK = "truck"
    CURTAIN = "curtain"


class User(BaseModel):
    """Application user account; role model present from day one."""

    id: int | None = None
    username: str = Field(min_length=1)
    role: Role
    is_active: bool = True


class Location(BaseModel):
    """A pickup or delivery place; coordinates optional until geocoded."""

    name: str = Field(min_length=1)
    city: str | None = None
    country: str | None = None
    postal_code: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    def location_key(self) -> str:
        """Stable lookup key for the coordinate dictionary."""
        parts = [
            (self.name or "").strip().lower(),
            (self.city or "").strip().lower(),
            (self.postal_code or "").strip().lower(),
            (self.country or "").strip().lower(),
        ]
        return "|".join(parts)


class Vehicle(BaseModel):
    """Fleet vehicle with load capacities.

    Seed capacities are PLACEHOLDER_PENDING_MARTYNA until the real fleet
    table arrives (docs/otwarte_wejscia_zespolu.md W-03).
    """

    id: int | None = None
    code: str = Field(min_length=1)
    vehicle_type: VehicleType
    pallet_capacity: int = Field(gt=0)
    weight_capacity_kg: float = Field(gt=0)
    is_active: bool = True
    is_placeholder: bool = True
    is_busy: bool = False


class Shipment(BaseModel):
    """A single load unit attached to an order.

    Shipments have no independent planning identity: they always travel
    with their parent order (FR-019).
    """

    shipment_number: str = Field(min_length=1)
    pallet_count: int | None = Field(default=None, ge=0)
    weight_kg: float | None = Field(default=None, ge=0)


class Order(BaseModel):
    """Transport order — the atomic unit of planning and assignment."""

    id: int | None = None
    delivery_code: str = Field(min_length=1)
    shipments: list[Shipment] = Field(min_length=1)
    pickup_location: Location
    delivery_location: Location
    delivery_date: date
    status: OrderStatus = OrderStatus.NEW

    @classmethod
    def create(
        cls,
        *,
        delivery_code: str,
        shipments: list[Shipment],
        pickup_location: Location,
        delivery_location: Location,
        delivery_date: date | None = None,
        default_delivery_days: int = DEFAULT_DELIVERY_DAYS,
        status: OrderStatus = OrderStatus.NEW,
    ) -> Order:
        """Create an order, applying the FR-024 default deadline.

        When ``delivery_date`` is missing the order gets
        ``today + default_delivery_days`` calendar days.
        """
        if delivery_date is None:
            delivery_date = date.today() + timedelta(days=default_delivery_days)
        return cls(
            delivery_code=delivery_code,
            shipments=shipments,
            pickup_location=pickup_location,
            delivery_location=delivery_location,
            delivery_date=delivery_date,
            status=status,
        )

    @property
    def total_pallets(self) -> int | None:
        counts = [s.pallet_count for s in self.shipments]
        if any(c is None for c in counts):
            return None
        return sum(c for c in counts if c is not None)

    @property
    def total_weight_kg(self) -> float | None:
        weights = [s.weight_kg for s in self.shipments]
        if any(w is None for w in weights):
            return None
        return sum(w for w in weights if w is not None)


def validate_assignment(order: Order, assignment_per_shipment: dict[str, str]) -> None:
    """Enforce FR-019: all shipments of an order share one assignment.

    ``assignment_per_shipment`` maps shipment_number to an assignment
    target identifier (vehicle id, transport id or warehouse schedule id).
    Raises ``InseparableShipmentsError`` when the order's shipments would
    end up in more than one target, and ``DomainError`` when a shipment
    of the order is missing from the assignment.

    Reused by the solver (T3) and by manual plan edits (T6).
    """
    targets: set[str] = set()
    for shipment in order.shipments:
        target = assignment_per_shipment.get(shipment.shipment_number)
        if target is None:
            raise DomainError(
                f"Shipment {shipment.shipment_number!r} of order "
                f"{order.delivery_code!r} has no assignment."
            )
        targets.add(target)
    if len(targets) > 1:
        raise InseparableShipmentsError(
            f"Shipments of order {order.delivery_code!r} would be split "
            f"across {sorted(targets)!r} — orders are inseparable (FR-019)."
        )
