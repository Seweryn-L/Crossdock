"""Order maintenance use cases (delete, counts, cargo / pallet edit)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from crossdock.domain.models import Order, OrderStatus
from crossdock.services.pallet_demand import cargo_table_pallets, demand_on_vehicle
from crossdock.storage.repositories import (
    AssignmentRepository,
    AuditLogRepository,
    OrderRepository,
    VehicleRepository,
)

_CARGO_EDITABLE = {OrderStatus.NEW, OrderStatus.PLANNED, OrderStatus.APPROVED}


@dataclass(frozen=True)
class OrderCounts:
    total: int
    new_status: int
    new_with_weight: int


@dataclass(frozen=True)
class PalletUpdateResult:
    order: Order
    old_total: int | None
    new_total: int | None
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


def update_order_cargo(
    session: Session,
    *,
    order_id: int,
    username: str,
    total_pallets: int | None,
    kg_per_pallet: float | None,
) -> PalletUpdateResult:
    """Set cargo denseness and/or explicit pallets (NEW / PLANNED / APPROVED)."""
    repo = OrderRepository(session)
    order = repo.get_by_id(order_id)
    if order is None:
        raise ValueError(f"Zlecenie #{order_id} nie istnieje.")
    if order.status not in _CARGO_EDITABLE:
        raise ValueError(
            f"Edycja palet / gęstości dozwolona dla statusów nowe, zaplanowane "
            f"i zatwierdzone (obecny: {order.status.value})."
        )
    if total_pallets is not None and total_pallets < 0:
        raise ValueError("Liczba palet nie może być ujemna.")
    if kg_per_pallet is not None and kg_per_pallet <= 0:
        raise ValueError("kg / paleta musi być większe od zera.")

    old_total = cargo_table_pallets(order)
    repo.update_order_pallets(order_id, total_pallets)
    updated = repo.update_order_kg_per_pallet(order_id, kg_per_pallet)
    new_total = cargo_table_pallets(updated)

    needs_replan = False
    warning: str | None = None
    if updated.status == OrderStatus.APPROVED:
        assign_repo = AssignmentRepository(session)
        approved = assign_repo.get_latest_approved_run()
        if approved is not None:
            for item in assign_repo.list_items_for_run(approved.id):
                if item.order_id != order_id or item.sequence is None:
                    continue
                vehicle = VehicleRepository(session).get_by_code(item.vehicle_code)
                if vehicle is not None:
                    demand = demand_on_vehicle(updated, vehicle)
                    if demand > vehicle.pallet_capacity:
                        needs_replan = True
                        warning = (
                            f"Nowa liczba palet ({demand}) przekracza pojemność "
                            f"pojazdu {vehicle.code} ({vehicle.pallet_capacity}) — "
                            f"wymaga przeplanowania."
                        )
                break

    AuditLogRepository(session).record(
        username=username,
        action="orders.cargo_update",
        details={
            "order_id": order_id,
            "delivery_code": updated.delivery_code,
            "old_total": old_total,
            "new_total": new_total,
            "kg_per_pallet": kg_per_pallet,
            "needs_replan": needs_replan,
        },
    )
    return PalletUpdateResult(
        order=updated,
        old_total=old_total,
        new_total=new_total,
        needs_replan=needs_replan,
        warning=warning,
    )


def update_approved_pallets(
    session: Session,
    *,
    order_id: int,
    total_pallets: int,
    username: str,
) -> PalletUpdateResult:
    """FR-021: edit explicit pallet count; preserves cargo kg/pallet if set."""
    repo = OrderRepository(session)
    order = repo.get_by_id(order_id)
    if order is None:
        raise ValueError(f"Zlecenie #{order_id} nie istnieje.")
    return update_order_cargo(
        session,
        order_id=order_id,
        username=username,
        total_pallets=total_pallets,
        kg_per_pallet=order.kg_per_pallet,
    )
