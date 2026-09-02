"""Compare two plan generations (delta metrics for Raporty)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from crossdock.config import Settings, get_settings
from crossdock.services.generation_kpi import GenerationKpi, build_generation_kpi

MetricName = Literal[
    "vehicles",
    "km",
    "avg_fill_pct",
    "cost_eur",
    "staying",
]


@dataclass(frozen=True, slots=True)
class GenerationComparison:
    run_a_id: int
    run_b_id: int
    label_a: str
    label_b: str
    delta_vehicles: int
    delta_km: float
    delta_avg_fill_pct: float
    delta_cost_eur: float
    delta_staying: int


def compare_generations(
    session: Session,
    run_a_id: int,
    run_b_id: int,
    *,
    settings: Settings | None = None,
) -> GenerationComparison | None:
    """Return deltas B - A for two runs."""
    cfg = settings or get_settings()
    kpi_a = build_generation_kpi(session, run_id=run_a_id, settings=cfg)
    kpi_b = build_generation_kpi(session, run_id=run_b_id, settings=cfg)
    if kpi_a is None or kpi_b is None:
        return None

    return _comparison_from_kpis(kpi_a, kpi_b)


def _comparison_from_kpis(kpi_a: GenerationKpi, kpi_b: GenerationKpi) -> GenerationComparison:
    def _delta(new: float | None, old: float | None) -> float:
        if new is None or old is None:
            return 0.0
        return new - old

    avg_a = (kpi_a.avg_fill_ratio or 0.0) * 100.0
    avg_b = (kpi_b.avg_fill_ratio or 0.0) * 100.0

    return GenerationComparison(
        run_a_id=kpi_a.run_id,
        run_b_id=kpi_b.run_id,
        label_a=kpi_a.label,
        label_b=kpi_b.label,
        delta_vehicles=kpi_b.vehicles_used - kpi_a.vehicles_used,
        delta_km=_delta(kpi_b.total_distance_km, kpi_a.total_distance_km),
        delta_avg_fill_pct=avg_b - avg_a,
        delta_cost_eur=_delta(kpi_b.total_cost_eur, kpi_a.total_cost_eur),
        delta_staying=kpi_b.staying - kpi_a.staying,
    )


def delta_sentiment(metric: MetricName, delta: float) -> Literal["good", "bad", "neutral"]:
    """Green = improvement for dispatcher context."""
    if abs(delta) < 1e-9:
        return "neutral"
    lower_is_better = metric in {"vehicles", "km", "cost_eur", "staying"}
    if lower_is_better:
        return "good" if delta < 0 else "bad"
    return "good" if delta > 0 else "bad"
