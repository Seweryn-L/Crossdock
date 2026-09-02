"""Tests for attention reason codes."""

from __future__ import annotations

from crossdock.domain.attention import (
    AttentionReason,
    attention_reason_pl,
    resolve_attention_reason,
)


def test_attention_reason_labels_polish() -> None:
    assert "współrzędnych" in attention_reason_pl(AttentionReason.MISSING_COORDS)
    assert attention_reason_pl("missing_coords") == attention_reason_pl(
        AttentionReason.MISSING_COORDS
    )


def test_resolve_attention_reason_priority() -> None:
    assert (
        resolve_attention_reason(
            1,
            no_coords_ids={1, 2},
            trimmed_ids={2},
            unrouted_ids={2, 3},
        )
        == AttentionReason.MISSING_COORDS
    )
    assert (
        resolve_attention_reason(
            2,
            no_coords_ids=set(),
            trimmed_ids={2},
            unrouted_ids={2, 3},
        )
        == AttentionReason.MAX_DROPS_EXCEEDED
    )
    assert (
        resolve_attention_reason(
            3,
            no_coords_ids=set(),
            trimmed_ids=set(),
            unrouted_ids={3},
        )
        == AttentionReason.ROUTING_FAILED
    )
