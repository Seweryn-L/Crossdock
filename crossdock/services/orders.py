"""Order maintenance use cases (delete, counts, FR-021 pallet edit)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from crossdock.domain.models import Order, OrderStatus
from crossdock.storage.repositories import (
    AssignmentRepository,
    AuditLogRepository,
    OrderRepository,
    VehicleRepository,
)


@dataclass(frozen=True)
class OrderCounts:
    total: int
    new_status: int
    new_with_weight: int


@dataclass(frozen=True)
class PalletUpdateResult:
    order: Order
    old_total: int | None
    new_total: int
    needs_replan: bool
    warning: str | None


def order_counts(session: Session) -> OrderCounts:
    repo = OrderRepository(session)
    new_orders = repo.list_by_status(OrderStatus.NEW)
    with_weight = sum(1 for o in new_orders if o.total_weight_kg is not None)
    return OrderCounts(
        total=repo.count(),
        new_status=len(new_orders),
        new_with_weight=with_weight,
    )


def delete_orders(session: Session, *, order_ids: list[int], username: str) -> int:
    repo = OrderRepository(session)
    deleted = repo.delete_by_ids(order_ids)
    if deleted:
        AuditLogRepository(session).record(
            username=username,
            action="orders.delete",
            details={"count": deleted, "order_ids": order_ids[:50]},
        )
    return deleted


def delete_all_orders(session: Session, *, username: str) -> int:
    repo = OrderRepository(session)
    deleted = repo.delete_all()
    if deleted:
        AuditLogRepository(session).record(
            username=username,
            action="orders.delete_all",
            details={"count": deleted},
        )
    return deleted


def update_approved_pallets(
    session: Session,
    *,
    order_id: int,
    total_pallets: int,
    username: str,
) -> PalletUpdateResult:
    """FR-021: edit pallet count for APPROVED orders only."""
    repo = OrderRepository(session)
    order = repo.get_by_id(order_id)
    if order is None:
        raise ValueError(f"Zlecenie #{order_id} nie istnieje.")
    if order.status != OrderStatus.APPROVED:
        raise ValueError(
            f"Edycja palet dozwolona tylko dla statusu „approved” (obecny: {order.status.value})."
        )
    if total_pallets < 0:
        raise ValueError("Liczba palet nie może być ujemna.")

    old_total = order.total_pallets
    updated = repo.update_order_pallets(order_id, total_pallets)

    needs_replan = False
    warning: str | None = None
    assign_repo = AssignmentRepository(session)
    approved = assign_repo.get_latest_approved_run()
    if approved is not None:
        for item in assign_repo.list_items_for_run(approved.id):
            if item.order_id != order_id or item.sequence is None:
                continue
            vehicle = VehicleRepository(session).get_by_code(item.vehicle_code)
            if vehicle is not None and total_pallets > vehicle.pallet_capacity:
                needs_replan = True
                warning = (
                    f"Nowa liczba palet ({total_pallets}) przekracza pojemność "
                    f"pojazdu {vehicle.code} ({vehicle.pallet_capacity}) — "
                    f"wymaga przeplanowania."
                )
            break

    AuditLogRepository(session).record(
        username=username,
        action="orders.pallet_update",
        details={
            "order_id": order_id,
            "delivery_code": updated.delivery_code,
            "old_total": old_total,
            "new_total": total_pallets,
            "needs_replan": needs_replan,
        },
    )
    return PalletUpdateResult(
        order=updated,
        old_total=old_total,
        new_total=total_pallets,
        needs_replan=needs_replan,
        warning=warning,
    )
