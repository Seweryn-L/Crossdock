"""Tests for FR-022 buffering heuristic (pure optimization)."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from crossdock.optimization.buffering import decide_buffer, decide_one
from crossdock.optimization.dto import BufferCandidate, BufferRates


def _rates(**kwargs: float | int) -> BufferRates:
    base = dict(
        cost_per_km=1.2,
        storage_cost_per_pallet_day=2.0,
        ltl_cost_multiplier=1.8,
        savings_threshold=0.15,
        max_buffer_days=3,
    )
    base.update(kwargs)
    return BufferRates(**base)  # type: ignore[arg-type]


def test_golden_buffer_when_ltl_expensive() -> None:
    """Numeric example: 100 km, 2 pallets, LTL 1.8x -> buffer 1 day (>=15% savings)."""
    cand = BufferCandidate(
        order_id=1,
        delivery_code="BUF1",
        weight_kg=500,
        pallet_count=2,
        distance_km=100.0,
    )
    # FTL RT = 240, LTL = 432; storage 1d = 4; buffer = 244; savings ≈ 43.5%
    decision = decide_one(cand, _rates())
    assert decision.action == "buffer"
    assert decision.buffer_days == 1
    assert decision.savings_ratio >= 0.15
    assert decision.cost_buffer_eur < decision.cost_ship_now_eur * 0.85


def test_golden_ship_now_when_storage_expensive() -> None:
    cand = BufferCandidate(
        order_id=2,
        delivery_code="SHIP1",
        weight_kg=500,
        pallet_count=50,
        distance_km=20.0,
    )
    # High storage / day vs short haul LTL → ship now
    decision = decide_one(
        cand,
        _rates(storage_cost_per_pallet_day=40.0, ltl_cost_multiplier=1.1),
    )
    assert decision.action == "ship_now"
    assert decision.buffer_days == 0


def test_decide_buffer_batch() -> None:
    rates = _rates()
    decisions = decide_buffer(
        [
            BufferCandidate(1, "A", 100, 2, 100.0),
            BufferCandidate(2, "B", 100, 50, 10.0),
        ],
        rates,
    )
    assert len(decisions) == 2
    assert decisions[0].action == "buffer"


@given(
    distance=st.floats(min_value=1.0, max_value=500.0, allow_nan=False),
    pallets=st.integers(min_value=1, max_value=40),
    ltl_mult=st.floats(min_value=1.0, max_value=3.0, allow_nan=False),
    storage=st.floats(min_value=0.5, max_value=30.0, allow_nan=False),
)
@settings(max_examples=40, deadline=None)
def test_buffer_invariants(distance: float, pallets: int, ltl_mult: float, storage: float) -> None:
    rates = _rates(
        ltl_cost_multiplier=ltl_mult,
        storage_cost_per_pallet_day=storage,
        max_buffer_days=3,
        savings_threshold=0.15,
    )
    d = decide_one(
        BufferCandidate(1, "X", 100.0, pallets, distance),
        rates,
    )
    assert d.buffer_days <= rates.max_buffer_days
    if d.action == "buffer":
        assert d.buffer_days >= 1
        assert d.savings_ratio + 1e-9 >= rates.savings_threshold
        assert d.cost_buffer_eur <= d.cost_ship_now_eur * (1.0 - rates.savings_threshold) + 1e-6
    else:
        assert d.buffer_days == 0
