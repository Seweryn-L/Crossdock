"""Attention bucket reason codes (persisted on assignment items)."""

from __future__ import annotations

from enum import StrEnum


class AttentionReason(StrEnum):
    MISSING_COORDS = "missing_coords"
    MAX_DROPS_EXCEEDED = "max_drops_exceeded"
    ROUTING_FAILED = "routing_failed"
    UNKNOWN = "unknown"


ATTENTION_REASON_LABELS_PL: dict[str, str] = {
    AttentionReason.MISSING_COORDS: "Brak współrzędnych odbiorcy",
    AttentionReason.MAX_DROPS_EXCEEDED: "Przekroczony limit punktów rozładunku",
    AttentionReason.ROUTING_FAILED: "Brak trasy (solver)",
    AttentionReason.UNKNOWN: "Nieznany stan",
}


def attention_reason_pl(code: str | None) -> str:
    if not code:
        return ATTENTION_REASON_LABELS_PL[AttentionReason.UNKNOWN]
    return ATTENTION_REASON_LABELS_PL.get(code, ATTENTION_REASON_LABELS_PL[AttentionReason.UNKNOWN])


def resolve_attention_reason(
    order_id: int,
    *,
    no_coords_ids: set[int],
    trimmed_ids: set[int],
    unrouted_ids: set[int],
) -> str:
    if order_id in no_coords_ids:
        return AttentionReason.MISSING_COORDS
    if order_id in trimmed_ids:
        return AttentionReason.MAX_DROPS_EXCEEDED
    if order_id in unrouted_ids:
        return AttentionReason.ROUTING_FAILED
    return AttentionReason.UNKNOWN
