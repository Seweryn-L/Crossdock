"""FR-022 buffering proposals for warehouse queue."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from crossdock.config import Settings, get_settings
from crossdock.distance.haversine import HaversineDistanceProvider
from crossdock.domain.models import OrderStatus
from crossdock.optimization.buffering import decide_buffer
from crossdock.optimization.dto import BufferCandidate, BufferDecision, BufferRates
from crossdock.services.pallet_demand import demand_without_vehicle
from crossdock.services.plan_view import build_plan_view
from crossdock.services.warehouse_queue import enqueue_order, set_held
from crossdock.storage.repositories import (
    AuditLogRepository,
    OrderRepository,
    WarehouseQueueRepository,
)


@dataclass(frozen=True)
class BufferProposalBundle:
    decisions: tuple[BufferDecision, ...]
    buffer_count: int
    ship_now_count: int


def _rates_from_settings(settings: Settings) -> BufferRates:
    return BufferRates(
        cost_per_km=settings.cost_per_km,
        storage_cost_per_pallet_day=settings.storage_cost_per_pallet_day,
        ltl_cost_multiplier=settings.ltl_cost_multiplier,
        savings_threshold=settings.buffer_savings_threshold,
        max_buffer_days=settings.max_buffer_days,
    )


def list_buffer_candidates(
    session: Session, settings: Settings | None = None
) -> list[BufferCandidate]:
    """NEW orders not in queue; prefer staying IDs from latest plan when present."""
    settings = settings or get_settings()
    queued = {r.order_id for r in WarehouseQueueRepository(session).list_ordered()}
    orders_repo = OrderRepository(session)
    staying_ids = set(build_plan_view(session).staying_order_ids)

    new_orders = [
        o
        for o in orders_repo.list_by_status(OrderStatus.NEW)
        if o.id is not None and o.id not in queued
    ]
    # Prefer staying first, then other NEW
    preferred = [o for o in new_orders if o.id in staying_ids]
    rest = [o for o in new_orders if o.id not in staying_ids]
    ordered = preferred + rest

    depot = (settings.depot_latitude, settings.depot_longitude)
    distance = HaversineDistanceProvider()
    candidates: list[BufferCandidate] = []
    for order in ordered:
        assert order.id is not None
        loc = order.delivery_location
        if loc.latitude is None or loc.longitude is None:
            continue
        km = distance.distance_km(depot[0], depot[1], float(loc.latitude), float(loc.longitude))
        weight = order.total_weight_kg or 0.0
        pallets = demand_without_vehicle(order, settings)
        candidates.append(
            BufferCandidate(
                order_id=order.id,
                delivery_code=order.delivery_code,
                weight_kg=weight,
                pallet_count=max(int(pallets), 0),
                distance_km=km,
            )
        )
    return candidates


def propose_buffering(
    session: Session,
    *,
    username: str,
    settings: Settings | None = None,
) -> BufferProposalBundle:
    settings = settings or get_settings()
    candidates = list_buffer_candidates(session, settings)
    decisions = decide_buffer(candidates, _rates_from_settings(settings))
    buffer_count = sum(1 for d in decisions if d.action == "buffer")
    AuditLogRepository(session).record(
        username=username,
        action="buffering.propose",
        details={
            "candidates": len(candidates),
            "buffer": buffer_count,
            "ship_now": len(decisions) - buffer_count,
        },
    )
    return BufferProposalBundle(
        decisions=decisions,
        buffer_count=buffer_count,
        ship_now_count=len(decisions) - buffer_count,
    )


def accept_buffer_proposals(
    session: Session,
    *,
    order_ids: list[int],
    decisions_by_id: dict[int, BufferDecision],
    username: str,
) -> int:
    """Enqueue accepted orders as held with note buffer:Xd. Returns accepted count."""
    accepted = 0
    for oid in order_ids:
        decision = decisions_by_id.get(oid)
        if decision is None or decision.action != "buffer":
            continue
        note = f"buffer:{decision.buffer_days}d"
        try:
            enqueue_order(session, order_id=oid, username=username, note=note)
            set_held(session, order_id=oid, held=True, username=username)
        except ValueError:
            continue
        accepted += 1
    if accepted:
        AuditLogRepository(session).record(
            username=username,
            action="buffering.accept",
            details={"accepted": accepted, "order_ids": order_ids[:50]},
        )
    return accepted
