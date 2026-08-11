"""Warehouse queue use cases (FR-020) — whole orders only (FR-019)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from crossdock.domain.models import Order, OrderStatus
from crossdock.storage.repositories import (
    AuditLogRepository,
    OrderRepository,
    WarehouseQueueRepository,
)


@dataclass(frozen=True)
class QueueEntry:
    order_id: int
    delivery_code: str
    position: int
    status: str
    note: str | None
    city: str
    weight_kg: float | None


def list_queue(session: Session) -> list[QueueEntry]:
    repo = WarehouseQueueRepository(session)
    orders = OrderRepository(session)
    entries: list[QueueEntry] = []
    for row in repo.list_ordered():
        order = orders.get_by_id(row.order_id)
        if order is None:
            continue
        entries.append(_to_entry(row.position, row.status, row.note, order))
    return entries


def list_enqueue_candidates(session: Session) -> list[QueueEntry]:
    """NEW orders that are not already in the warehouse queue."""
    queued_ids = {row.order_id for row in WarehouseQueueRepository(session).list_ordered()}
    candidates: list[QueueEntry] = []
    for order in OrderRepository(session).list_by_status(OrderStatus.NEW):
        if order.id is None or order.id in queued_ids:
            continue
        candidates.append(
            QueueEntry(
                order_id=order.id,
                delivery_code=order.delivery_code,
                position=0,
                status="available",
                note=None,
                city=order.delivery_location.city or "",
                weight_kg=order.total_weight_kg,
            )
        )
    return candidates


def enqueue_order(
    session: Session,
    *,
    order_id: int,
    username: str,
    note: str | None = None,
) -> QueueEntry:
    order = OrderRepository(session).get_by_id(order_id)
    if order is None:
        raise ValueError(f"Zlecenie #{order_id} nie istnieje.")
    if order.status != OrderStatus.NEW:
        raise ValueError(
            f"Do kolejki można dodać tylko zlecenia „new” (obecny: {order.status.value})."
        )
    if order.id is None:
        raise ValueError("Zlecenie bez ID.")
    row = WarehouseQueueRepository(session).add(order_id=order.id, note=note)
    AuditLogRepository(session).record(
        username=username,
        action="warehouse.enqueue",
        details={"order_id": order.id, "delivery_code": order.delivery_code},
    )
    return _to_entry(row.position, row.status, row.note, order)


def enqueue_many(
    session: Session,
    *,
    order_ids: list[int],
    username: str,
) -> int:
    """Enqueue NEW orders not already queued; skip others silently. Returns added count."""
    repo = WarehouseQueueRepository(session)
    orders = OrderRepository(session)
    added = 0
    for order_id in order_ids:
        if repo.get_by_order_id(order_id) is not None:
            continue
        order = orders.get_by_id(order_id)
        if order is None or order.id is None or order.status != OrderStatus.NEW:
            continue
        enqueue_order(session, order_id=order.id, username=username)
        added += 1
    return added


def dequeue_order(session: Session, *, order_id: int, username: str) -> bool:
    ok = WarehouseQueueRepository(session).delete_by_order_id(order_id)
    if ok:
        AuditLogRepository(session).record(
            username=username,
            action="warehouse.dequeue",
            details={"order_id": order_id},
        )
    return ok


def move_order(
    session: Session,
    *,
    order_id: int,
    direction: str,
    username: str,
) -> list[QueueEntry]:
    """Move order up or down in the queue (swap with neighbour)."""
    repo = WarehouseQueueRepository(session)
    rows = repo.list_ordered()
    idx = next((i for i, r in enumerate(rows) if r.order_id == order_id), None)
    if idx is None:
        raise ValueError(f"Zlecenie #{order_id} nie jest w kolejce.")
    if direction == "up":
        if idx == 0:
            return list_queue(session)
        neighbour = rows[idx - 1]
    elif direction == "down":
        if idx >= len(rows) - 1:
            return list_queue(session)
        neighbour = rows[idx + 1]
    else:
        raise ValueError("direction must be 'up' or 'down'")
    repo.swap_positions(order_id, neighbour.order_id)
    AuditLogRepository(session).record(
        username=username,
        action="warehouse.rotate",
        details={
            "order_id": order_id,
            "direction": direction,
            "swapped_with": neighbour.order_id,
        },
    )
    return list_queue(session)


def set_held(
    session: Session,
    *,
    order_id: int,
    held: bool,
    username: str,
) -> QueueEntry:
    status = "held" if held else "waiting"
    row = WarehouseQueueRepository(session).set_status(order_id, status)
    order = OrderRepository(session).get_by_id(order_id)
    if order is None:
        raise ValueError(f"Zlecenie #{order_id} nie istnieje.")
    AuditLogRepository(session).record(
        username=username,
        action="warehouse.status",
        details={"order_id": order_id, "status": status},
    )
    return _to_entry(row.position, row.status, row.note, order)


def _to_entry(position: int, status: str, note: str | None, order: Order) -> QueueEntry:
    assert order.id is not None
    return QueueEntry(
        order_id=order.id,
        delivery_code=order.delivery_code,
        position=position,
        status=status,
        note=note,
        city=order.delivery_location.city or "",
        weight_kg=order.total_weight_kg,
    )
