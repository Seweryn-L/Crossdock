"""Shared generation KPI block for Operacje and Raporty."""

from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from crossdock.domain.attention import attention_reason_pl
from crossdock.services.generation_compare import GenerationComparison, delta_sentiment
from crossdock.services.generation_kpi import GenerationKpi


def _fmt_km(km: float | None) -> str:
    if km is None:
        return "—"
    return f"{km:,.0f} km".replace(",", " ")


def _fmt_eur(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:,.0f} €".replace(",", " ")


def _fmt_pct_ratio(ratio: float | None) -> str:
    if ratio is None:
        return "—"
    return f"{ratio * 100:.0f}%"


class GenerationKpiPanel:
    """Mutable NiceGUI panel for generation KPI."""

    def __init__(self, container: ui.element) -> None:
        self._container = container
        self._on_reason_click: Callable[[str], None] | None = None
        with container:
            self._empty_label = ui.label("Brak generacji — kliknij Generuj w Operacjach.").classes(
                "text-gray-600"
            )
            self._card = ui.column().classes("w-full cd-gen-kpi-card gap-1")
            self._card.set_visibility(False)
            with self._card:
                self._title = ui.label("").classes("font-medium")
                self._line_orders = ui.label("").classes("text-sm")
                self._line_attention = ui.column().classes("gap-0 ml-2")
                self._line_routes = ui.label("").classes("text-sm")
                self._line_costs = ui.label("").classes("text-sm")

    def on_reason_click(self, handler: Callable[[str], None]) -> None:
        self._on_reason_click = handler

    def update(self, kpi: GenerationKpi | None, *, show_attention_breakdown: bool = True) -> None:
        if kpi is None or (kpi.is_empty and kpi.orders_in_planning == 0):
            self._empty_label.set_visibility(True)
            self._card.set_visibility(False)
            return

        self._empty_label.set_visibility(False)
        self._card.set_visibility(True)
        self._title.set_text(kpi.label)
        self._line_orders.set_text(
            f"Zaplanowano: {kpi.planned_label}  ·  "
            f"W magazynie: {kpi.staying}  ·  "
            f"Wymaga uwagi: {kpi.attention}"
        )
        self._line_routes.set_text(
            f"Trasy: {kpi.route_count}  ·  "
            f"Pojazdy: {kpi.vehicles_used}  ·  "
            f"Śr. zapełnienie: {_fmt_pct_ratio(kpi.avg_fill_ratio)}"
        )
        self._line_costs.set_text(
            f"Dystans: {_fmt_km(kpi.total_distance_km)}  ·  Koszt: {_fmt_eur(kpi.total_cost_eur)}"
        )

        self._line_attention.clear()
        if show_attention_breakdown and kpi.attention > 0 and kpi.attention_by_reason:
            with self._line_attention:
                ui.label(f"{kpi.attention} zleceń wymaga uwagi:").classes("text-sm text-gray-700")
                for code, count in sorted(
                    kpi.attention_by_reason.items(),
                    key=lambda x: (-x[1], x[0]),
                ):
                    label = attention_reason_pl(code)

                    def _click(_: object, c: str = code) -> None:
                        if self._on_reason_click is not None:
                            self._on_reason_click(c)

                    ui.button(
                        f"• {count} — {label}",
                        on_click=_click,
                    ).props("flat dense no-caps").classes("text-sm text-left justify-start")


class GenerationComparePanel:
    """Delta panel for two selected generations."""

    def __init__(self, container: ui.element) -> None:
        with container:
            self._hint = ui.label("Zaznacz dwie generacje do porównania.").classes(
                "text-gray-600 text-sm"
            )
            self._panel = ui.column().classes("w-full cd-gen-compare gap-1")
            self._panel.set_visibility(False)

    def update(self, comparison: GenerationComparison | None) -> None:
        self._panel.clear()
        if comparison is None:
            self._hint.set_visibility(True)
            self._panel.set_visibility(False)
            return

        self._hint.set_visibility(False)
        self._panel.set_visibility(True)
        with self._panel:
            ui.label(f"{comparison.label_b} vs {comparison.label_a}").classes("font-medium")
            rows: list[tuple[str, float, str]] = [
                ("pojazdy", float(comparison.delta_vehicles), "vehicles"),
                ("km", comparison.delta_km, "km"),
                ("śr. zapełnienia", comparison.delta_avg_fill_pct, "avg_fill_pct"),
                ("koszt", comparison.delta_cost_eur, "cost_eur"),
                ("zlecenia w magazynie", float(comparison.delta_staying), "staying"),
            ]
            for label, delta, metric in rows:
                if abs(delta) < 1e-9:
                    continue
                sign = "+" if delta > 0 else "-"
                magnitude = abs(delta)
                if metric == "avg_fill_pct":
                    text = f"  {sign}{magnitude:.0f}% {label}"
                elif metric == "km":
                    text = f"  {sign}{magnitude:.0f} km"
                elif metric == "cost_eur":
                    text = f"  {sign}{magnitude:.0f} € {label}"
                elif metric == "vehicles":
                    text = f"  {sign}{int(magnitude)} {label}"
                else:
                    text = f"  {sign}{int(magnitude)} {label}"
                sentiment = delta_sentiment(metric, delta)  # type: ignore[arg-type]
                css = {
                    "good": "cd-delta-good",
                    "bad": "cd-delta-bad",
                    "neutral": "text-gray-600",
                }[sentiment]
                ui.label(text).classes(f"text-sm {css}")
