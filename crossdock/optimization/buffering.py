"""FR-022 buffering heuristic: ship now (LTL) vs store then FTL — pure Python, no I/O."""

from __future__ import annotations

from crossdock.optimization.dto import BufferCandidate, BufferDecision, BufferRates


def estimate_ftl_roundtrip_eur(distance_km: float, cost_per_km: float) -> float:
    """Placeholder FTL cost: round-trip depot-drop at FTL rate."""
    return 2.0 * max(distance_km, 0.0) * cost_per_km


def estimate_ltl_now_eur(
    distance_km: float, cost_per_km: float, ltl_cost_multiplier: float
) -> float:
    """Immediate LTL shipment cost (premium over FTL km)."""
    return estimate_ftl_roundtrip_eur(distance_km, cost_per_km) * ltl_cost_multiplier


def estimate_storage_eur(pallet_count: int, days: int, storage_cost_per_pallet_day: float) -> float:
    return max(pallet_count, 1) * max(days, 0) * storage_cost_per_pallet_day


def decide_one(candidate: BufferCandidate, rates: BufferRates) -> BufferDecision:
    """Choose smallest buffer days meeting savings threshold, else ship_now."""
    pallets = max(candidate.pallet_count, 1)
    cost_ship = estimate_ltl_now_eur(
        candidate.distance_km, rates.cost_per_km, rates.ltl_cost_multiplier
    )
    ftl_later = estimate_ftl_roundtrip_eur(candidate.distance_km, rates.cost_per_km)

    best_days = 0
    best_buffer_cost = cost_ship
    best_savings = 0.0
    action = "ship_now"

    max_days = max(rates.max_buffer_days, 0)
    if candidate.slack_days is not None:
        max_days = 0 if candidate.slack_days <= 0 else min(max_days, candidate.slack_days)
    for days in range(1, max_days + 1):
        storage = estimate_storage_eur(pallets, days, rates.storage_cost_per_pallet_day)
        buffer_cost = storage + ftl_later
        savings = 0.0 if cost_ship <= 0 else (cost_ship - buffer_cost) / cost_ship
        # Buffer when buffer_cost <= cost_ship * (1 - threshold)
        if buffer_cost <= cost_ship * (1.0 - rates.savings_threshold):
            best_days = days
            best_buffer_cost = buffer_cost
            best_savings = savings
            action = "buffer"
            break

    if action == "ship_now" and max_days > 0:
        # Report cost at max days for transparency
        best_days = 0
        best_buffer_cost = (
            estimate_storage_eur(pallets, max_days, rates.storage_cost_per_pallet_day) + ftl_later
        )
        best_savings = (cost_ship - best_buffer_cost) / cost_ship if cost_ship > 0 else 0.0

    return BufferDecision(
        order_id=candidate.order_id,
        delivery_code=candidate.delivery_code,
        action=action,
        buffer_days=best_days,
        cost_ship_now_eur=round(cost_ship, 2),
        cost_buffer_eur=round(best_buffer_cost, 2),
        savings_ratio=round(best_savings, 4),
        pallet_count=pallets,
        weight_kg=candidate.weight_kg,
        distance_km=candidate.distance_km,
    )


def decide_buffer(
    candidates: tuple[BufferCandidate, ...] | list[BufferCandidate],
    rates: BufferRates,
) -> tuple[BufferDecision, ...]:
    return tuple(decide_one(c, rates) for c in candidates)
