"""Aggregated KPI for one plan generation (Operacje + Raporty)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from crossdock.config import Settings, get_settings
from crossdock.services.plan_view import build_plan_view
from crossdock.services.reports import build_report


@dataclass(frozen=True, slots=True)
class GenerationKpi:
    run_id: int
    label: str
    plan_status: str
    orders_in_planning: int
    riding: int
    staying: int
    attention: int
    attention_by_reason: dict[str, int]
    route_count: int
    vehicles_used: int
    avg_fill_ratio: float | None
    total_distance_km: float | None
    total_cost_eur: float | None
    savings_eur: float | None
    savings_pct: float | None
    is_empty: bool

    @property
    def planned_label(self) -> str:
        return f"{self.riding}/{self.orders_in_planning}"


def build_generation_kpi(
    session: Session,
    *,
    run_id: int | None = None,
    settings: Settings | None = None,
) -> GenerationKpi | None:
    """Combine plan view buckets with report savings for one generation."""
    cfg = settings or get_settings()
    view = build_plan_view(session, cfg, run_id=run_id)
    if view.summary is None:
        return None

    summary = view.summary
    riding = summary.riding
    staying = summary.staying
    attention = summary.attention
    orders_in_planning = riding + staying + attention

    fills: list[float] = []
    for row in view.routes:
        pct = row.get("weight_fill_pct")
        if isinstance(pct, (int, float)):
            fills.append(float(pct) / 100.0)

    avg_fill: float | None = None
    if fills:
        avg_fill = sum(fills) / len(fills)

    report = build_report(session, run_id=summary.run_id, settings=cfg)
    savings_eur: float | None = None
    savings_pct: float | None = None
    if report is not None:
        savings_eur = report.savings.savings_eur
        savings_pct = report.savings.savings_pct

    return GenerationKpi(
        run_id=summary.run_id,
        label=summary.label,
        plan_status=summary.plan_status,
        orders_in_planning=orders_in_planning,
        riding=riding,
        staying=staying,
        attention=attention,
        attention_by_reason=dict(summary.attention_by_reason),
        route_count=len(view.routes),
        vehicles_used=summary.vehicles,
        avg_fill_ratio=avg_fill,
        total_distance_km=summary.total_distance_km,
        total_cost_eur=summary.total_cost_eur,
        savings_eur=savings_eur,
        savings_pct=savings_pct,
        is_empty=orders_in_planning == 0 and len(view.routes) == 0,
    )
