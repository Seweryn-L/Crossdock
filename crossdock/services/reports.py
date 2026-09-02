"""Plan efficiency reports (FR-017 savings, FR-018 utilization) + Excel export."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from typing import TYPE_CHECKING, Any

import pandas as pd  # type: ignore[import-untyped]
from sqlalchemy.orm import Session

from crossdock.config import Settings, effective_planning_date, get_settings
from crossdock.distance.haversine import HaversineDistanceProvider
from crossdock.domain.attention import attention_reason_pl
from crossdock.services.plan_view import PlanView, build_plan_view
from crossdock.services.report_export_options import (
    SHEET_ORDER,
    ReportExportSelection,
    ReportSheetId,
)
from crossdock.storage.repositories import AssignmentRepository, OrderRepository, VehicleRepository
from crossdock.text_pl import format_plan_label, plan_status_pl

if TYPE_CHECKING:
    from crossdock.services.generation_compare import GenerationComparison
    from crossdock.services.generation_kpi import GenerationKpi


@dataclass(frozen=True)
class UtilizationRow:
    vehicle_code: str
    drop_count: int
    distance_km: float
    cost_eur: float
    fill_ratio: float | None
    order_count: int
    total_weight_kg: float
    route_status: str = "proposed"


@dataclass(frozen=True)
class SavingsSummary:
    baseline_cost_eur: float
    optimized_cost_eur: float
    savings_eur: float
    savings_pct: float
    routed_orders: int
    note: str


@dataclass(frozen=True)
class ReportBundle:
    run_id: int
    plan_status: str
    used_fallback_draft: bool
    utilization: tuple[UtilizationRow, ...]
    savings: SavingsSummary
    warnings: tuple[str, ...] = field(default_factory=tuple)
    display_name: str | None = None
    created_at: datetime | None = None


@dataclass(frozen=True)
class ReportXlsxBundle:
    """Full payload for multi-sheet Excel export."""

    report: ReportBundle
    kpi: GenerationKpi | None
    plan_view: PlanView
    run_username: str
    run_wall_time_s: float
    solver_warnings: tuple[str, ...]
    settings_snapshot: dict[str, Any]
    routed_orders: tuple[dict[str, Any], ...] = ()
    staying_orders: tuple[dict[str, Any], ...] = ()
    attention_summary: tuple[dict[str, Any], ...] = ()
    attention_orders: tuple[dict[str, Any], ...] = ()
    fleet_rows: tuple[dict[str, Any], ...] = ()
    comparison: GenerationComparison | None = None
    exported_at: datetime = field(default_factory=datetime.now)


def build_report(
    session: Session,
    *,
    run_id: int | None = None,
    settings: Settings | None = None,
) -> ReportBundle | None:
    """Build utilization + savings for an approved plan (fallback: latest draft)."""
    cfg = settings or get_settings()
    repo = AssignmentRepository(session)
    used_fallback = False
    warnings: list[str] = []

    if run_id is not None:
        run = repo.get_run(run_id)
    else:
        run = repo.get_latest_approved_run()
        if run is None:
            run = repo.get_latest_run()
            if run is not None:
                used_fallback = True
                warnings.append("Brak zatwierdzonego planu — raport z najnowszego draftu.")

    if run is None:
        return None

    routes = repo.list_routes_for_run(run.id)
    items = repo.list_items_for_run(run.id)
    orders = OrderRepository(session)
    vehicles = VehicleRepository(session)
    distance = HaversineDistanceProvider()
    depot = (cfg.depot_latitude, cfg.depot_longitude)

    items_by_vehicle: dict[str, list[Any]] = {}
    for item in items:
        if item.vehicle_code in {"UNASSIGNED", "UNROUTED"} or item.sequence is None:
            continue
        items_by_vehicle.setdefault(item.vehicle_code, []).append(item)

    utilization: list[UtilizationRow] = []
    for route in routes:
        v_items = items_by_vehicle.get(route.vehicle_code, [])
        total_weight = sum(i.weight_kg for i in v_items)
        fill: float | None = None
        vehicle = vehicles.get_by_code(route.vehicle_code)
        if vehicle is not None and vehicle.weight_capacity_kg > 0:
            fill = total_weight / vehicle.weight_capacity_kg
            if fill < cfg.min_fill_ratio:
                warnings.append(
                    f"Trasa {route.vehicle_code}: zapełnienie {fill * 100:.0f}% "
                    f"poniżej progu {cfg.min_fill_ratio * 100:.0f}%."
                )
        utilization.append(
            UtilizationRow(
                vehicle_code=route.vehicle_code,
                drop_count=route.drop_count,
                distance_km=route.distance_km,
                cost_eur=route.cost_eur,
                fill_ratio=fill,
                order_count=len(v_items),
                total_weight_kg=total_weight,
                route_status=route.route_status,
            )
        )

    baseline = 0.0
    routed_count = 0
    for item in items:
        if item.sequence is None or item.vehicle_code in {"UNASSIGNED", "UNROUTED"}:
            continue
        order = orders.get_by_id(item.order_id)
        if order is None:
            continue
        lat = order.delivery_location.latitude
        lon = order.delivery_location.longitude
        if lat is None or lon is None:
            warnings.append(f"Brak coords dla {item.delivery_code} — pominięto w baseline.")
            continue
        leg = distance.distance_km(depot[0], depot[1], lat, lon)
        baseline += 2.0 * leg * cfg.cost_per_km
        routed_count += 1

    optimized = float(run.total_cost_eur or 0.0)
    savings = baseline - optimized
    savings_pct = (savings / baseline * 100.0) if baseline > 0 else 0.0

    return ReportBundle(
        run_id=run.id,
        plan_status=run.plan_status,
        used_fallback_draft=used_fallback,
        utilization=tuple(utilization),
        savings=SavingsSummary(
            baseline_cost_eur=round(baseline, 2),
            optimized_cost_eur=round(optimized, 2),
            savings_eur=round(savings, 2),
            savings_pct=round(savings_pct, 1),
            routed_orders=routed_count,
            note=(
                "Baseline: 1 zlecenie = 1 pojazd (2x km depot-drop x cost_per_km). "
                "Stawki Sandry (W-06) — placeholder."
            ),
        ),
        warnings=tuple(warnings),
        display_name=run.display_name,
        created_at=run.created_at,
    )


def _settings_snapshot(cfg: Settings) -> dict[str, Any]:
    return {
        "planning_date": effective_planning_date(cfg).isoformat(),
        "min_fill_ratio_pct": round(cfg.min_fill_ratio * 100, 1),
        "max_drops_per_route": cfg.max_drops_per_route,
        "cost_per_km": cfg.cost_per_km,
        "use_osrm": cfg.use_osrm,
        "solver_time_limit_s": cfg.solver_time_limit_s,
        "solver_seed": cfg.solver_seed,
    }


def build_report_xlsx_data(
    session: Session,
    *,
    run_id: int | None = None,
    compare_run_id: int | None = None,
    settings: Settings | None = None,
) -> ReportXlsxBundle | None:
    """Aggregate KPI, plan view, savings, and optional generation comparison."""
    from crossdock.services.generation_compare import compare_generations
    from crossdock.services.generation_kpi import build_generation_kpi

    cfg = settings or get_settings()
    repo = AssignmentRepository(session)

    if run_id is not None:
        run = repo.get_run(run_id)
    else:
        run = repo.get_latest_approved_run() or repo.get_latest_run()
    if run is None:
        return None

    report = build_report(session, run_id=run.id, settings=cfg)
    if report is None:
        return None

    kpi = build_generation_kpi(session, run_id=run.id, settings=cfg)
    plan_view = build_plan_view(session, cfg, run_id=run.id)

    comparison: GenerationComparison | None = None
    if compare_run_id is not None and compare_run_id != run.id:
        comparison = compare_generations(session, compare_run_id, run.id, settings=cfg)

    solver_warnings: tuple[str, ...] = ()
    if run.warnings_json:
        try:
            parsed = json.loads(run.warnings_json)
            if isinstance(parsed, list):
                solver_warnings = tuple(str(w) for w in parsed)
        except json.JSONDecodeError:
            solver_warnings = (run.warnings_json,)

    return ReportXlsxBundle(
        report=report,
        kpi=kpi,
        plan_view=plan_view,
        run_username=run.username,
        run_wall_time_s=run.wall_time_s,
        solver_warnings=solver_warnings,
        settings_snapshot=_settings_snapshot(cfg),
        routed_orders=tuple(_rows_routed_orders(session, run.id)),
        staying_orders=tuple(_rows_bucket_orders(session, plan_view.staying)),
        attention_summary=tuple(_rows_attention_summary_for(plan_view, kpi)),
        attention_orders=tuple(_rows_bucket_orders(session, plan_view.attention)),
        fleet_rows=tuple(_rows_fleet_utilization(session, report, plan_view)),
        comparison=comparison,
    )


def report_export_filename(run_id: int, *, compare_run_id: int | None = None) -> str:
    if compare_run_id is not None:
        return f"raport_crossdock_gen_{compare_run_id}_vs_{run_id}.xlsx"
    return f"raport_crossdock_gen_{run_id}.xlsx"


def _disposition_pl(code: object) -> str:
    if code == "hold":
        return "Czeka na dopełnienie"
    if code == "send":
        return "Wyślij"
    return str(code or "—")


def _sentiment_pl(metric: str, delta: float) -> str:
    from crossdock.services.generation_compare import delta_sentiment

    sentiment = delta_sentiment(metric, delta)  # type: ignore[arg-type]
    if sentiment == "good":
        return "Lepsze"
    if sentiment == "bad":
        return "Gorsze"
    return "Bez zmian"


def _order_lookup(session: Session) -> OrderRepository:
    return OrderRepository(session)


def _rows_summary(bundle: ReportXlsxBundle) -> list[dict[str, Any]]:
    report = bundle.report
    kpi = bundle.kpi
    summary = bundle.plan_view.summary
    cfg = bundle.settings_snapshot
    rows: list[dict[str, Any]] = [
        {
            "Wskaźnik": "Numer planu",
            "Wartość": report.run_id,
        },
        {
            "Wskaźnik": "Nazwa / etykieta",
            "Wartość": format_plan_label(
                run_id=report.run_id,
                display_name=report.display_name,
                plan_status=report.plan_status,
                created_at=report.created_at,
            ),
        },
        {
            "Wskaźnik": "Status planu",
            "Wartość": plan_status_pl(report.plan_status),
        },
        {
            "Wskaźnik": "Wygenerowano",
            "Wartość": (report.created_at.strftime("%Y-%m-%d %H:%M") if report.created_at else "—"),
        },
        {"Wskaźnik": "Wygenerował", "Wartość": bundle.run_username},
        {"Wskaźnik": "Czas solvera [s]", "Wartość": round(bundle.run_wall_time_s, 2)},
        {"Wskaźnik": "Data eksportu", "Wartość": bundle.exported_at.strftime("%Y-%m-%d %H:%M")},
    ]
    if kpi is not None:
        rows.extend(
            [
                {"Wskaźnik": "Zlecenia w planowaniu", "Wartość": kpi.orders_in_planning},
                {"Wskaźnik": "Zaplanowane (jedzie)", "Wartość": kpi.riding},
                {"Wskaźnik": "W magazynie", "Wartość": kpi.staying},
                {"Wskaźnik": "Wymaga uwagi", "Wartość": kpi.attention},
                {"Wskaźnik": "Liczba tras", "Wartość": kpi.route_count},
                {"Wskaźnik": "Pojazdy użyte", "Wartość": kpi.vehicles_used},
                {
                    "Wskaźnik": "Średnie zapełnienie [%]",
                    "Wartość": (
                        round(kpi.avg_fill_ratio * 100, 1)
                        if kpi.avg_fill_ratio is not None
                        else None
                    ),
                },
                {
                    "Wskaźnik": "Łączny dystans [km]",
                    "Wartość": (
                        round(kpi.total_distance_km, 1)
                        if kpi.total_distance_km is not None
                        else None
                    ),
                },
                {
                    "Wskaźnik": "Koszt planu [€]",
                    "Wartość": (
                        round(kpi.total_cost_eur, 2) if kpi.total_cost_eur is not None else None
                    ),
                },
                {
                    "Wskaźnik": "Oszczędność [€]",
                    "Wartość": round(kpi.savings_eur, 2) if kpi.savings_eur is not None else None,
                },
                {
                    "Wskaźnik": "Oszczędność [%]",
                    "Wartość": round(kpi.savings_pct, 1) if kpi.savings_pct is not None else None,
                },
            ]
        )
    elif summary is not None:
        rows.extend(
            [
                {"Wskaźnik": "Zaplanowane (jedzie)", "Wartość": summary.riding},
                {"Wskaźnik": "W magazynie", "Wartość": summary.staying},
                {"Wskaźnik": "Wymaga uwagi", "Wartość": summary.attention},
            ]
        )
    rows.extend(
        [
            {"Wskaźnik": "Min. zapełnienie [%]", "Wartość": cfg.get("min_fill_ratio_pct")},
            {"Wskaźnik": "Max dropów / trasa", "Wartość": cfg.get("max_drops_per_route")},
            {"Wskaźnik": "Koszt [€/km]", "Wartość": cfg.get("cost_per_km")},
            {"Wskaźnik": "OSRM", "Wartość": "tak" if cfg.get("use_osrm") else "nie"},
        ]
    )
    all_warnings = list(bundle.solver_warnings) + list(report.warnings)
    if report.used_fallback_draft:
        all_warnings.insert(0, "Raport z draftu — brak zatwierdzonego planu.")
    if all_warnings:
        rows.append({"Wskaźnik": "Ostrzeżenia", "Wartość": "; ".join(all_warnings)})
    elif kpi is not None and kpi.is_empty:
        rows.append({"Wskaźnik": "Uwaga", "Wartość": "Pusta generacja — brak tras i zleceń."})
    return rows


def _rows_routes(bundle: ReportXlsxBundle) -> list[dict[str, Any]]:
    util_by_vehicle = {u.vehicle_code: u for u in bundle.report.utilization}
    rows: list[dict[str, Any]] = []
    for route in bundle.plan_view.routes:
        vehicle = str(route.get("vehicle") or "")
        util = util_by_vehicle.get(vehicle)
        rows.append(
            {
                "Pojazd": vehicle,
                "Status trasy": route.get("route_status_pl") or route.get("route_status"),
                "Dropy": route.get("drop_count"),
                "Zlecenia": route.get("order_count"),
                "Miasta": route.get("drop_summary") or "—",
                "Zapełnienie [%]": route.get("weight_fill_pct"),
                "Poniżej progu": "tak" if route.get("below_min_fill") else "nie",
                "Decyzja": _disposition_pl(route.get("disposition")),
                "SLA": route.get("sla_label"),
                "Slack [dni]": route.get("min_slack"),
                "Termin wyjazdu": route.get("deadline_label"),
                "Km": route.get("distance_km"),
                "Koszt €": route.get("cost_eur"),
                "Waga [kg]": round(util.total_weight_kg, 1) if util else None,
                "Zatwierdzono": route.get("approved_at") or "—",
                "W drodze": route.get("departed_at") or "—",
                "Zrealizowano": route.get("completed_at") or "—",
            }
        )
    return rows


def _rows_routed_orders(session: Session, run_id: int) -> list[dict[str, Any]]:
    repo = AssignmentRepository(session)
    orders = _order_lookup(session)
    items = [
        i
        for i in repo.list_items_for_run(run_id)
        if i.sequence is not None and i.vehicle_code not in {"UNASSIGNED", "UNROUTED"}
    ]
    items.sort(key=lambda i: (i.vehicle_code, i.sequence or 0, i.delivery_code))
    rows: list[dict[str, Any]] = []
    for item in items:
        order = orders.get_by_id(item.order_id)
        city = "—"
        delivery_date = "—"
        must_leave = "—"
        shipments_n = None
        pallets = None
        if order is not None:
            city = order.delivery_location.city or "—"
            delivery_date = (
                order.delivery_date.isoformat() if order.delivery_date is not None else "—"
            )
            must_leave = order.must_leave_by.isoformat() if order.must_leave_by is not None else "—"
            shipments_n = len(order.shipments)
            pallets = order.total_pallets
        attention = attention_reason_pl(item.attention_reason) if item.attention_reason else "—"
        rows.append(
            {
                "Pojazd": item.vehicle_code,
                "Kolejność": item.sequence,
                "Kod dostawy": item.delivery_code,
                "Miasto": city,
                "Waga [kg]": round(item.weight_kg, 1),
                "Termin dostawy": delivery_date,
                "Wyjazd do": must_leave,
                "Przesyłki": shipments_n,
                "Palety": pallets if pallets is not None else "—",
                "Uwaga": attention,
            }
        )
    return rows


def _rows_bucket_orders(
    session: Session,
    bucket_rows: list[dict[str, object]],
    *,
    include_reason: bool = True,
) -> list[dict[str, Any]]:
    orders = _order_lookup(session)
    out: list[dict[str, Any]] = []
    for row in bucket_rows:
        oid = row.get("order_id")
        order = orders.get_by_id(int(oid)) if isinstance(oid, int) else None
        city = "—"
        delivery_date = "—"
        must_leave = "—"
        if order is not None:
            city = order.delivery_location.city or "—"
            delivery_date = (
                order.delivery_date.isoformat() if order.delivery_date is not None else "—"
            )
            must_leave = order.must_leave_by.isoformat() if order.must_leave_by is not None else "—"
        entry: dict[str, Any] = {
            "Kod dostawy": row.get("delivery_code"),
            "Miasto": city,
            "Waga [kg]": row.get("weight_kg"),
            "Termin dostawy": delivery_date,
            "Wyjazd do": must_leave,
            "Slack": row.get("sla"),
        }
        if include_reason:
            entry["Powód"] = row.get("reason")
            entry["Kod powodu"] = row.get("reason_code") or "—"
        out.append(entry)
    return out


def _rows_attention_summary_for(
    plan_view: PlanView,
    kpi: GenerationKpi | None,
) -> list[dict[str, Any]]:
    if kpi is not None and kpi.attention_by_reason:
        reasons = kpi.attention_by_reason
    elif plan_view.summary is not None and plan_view.summary.attention_by_reason:
        reasons = plan_view.summary.attention_by_reason
    else:
        return []
    return [
        {"Powód": attention_reason_pl(code), "Liczba": count}
        for code, count in sorted(reasons.items())
    ]


def _rows_attention_summary(bundle: ReportXlsxBundle) -> list[dict[str, Any]]:
    return list(bundle.attention_summary)


def _rows_savings(bundle: ReportXlsxBundle) -> list[dict[str, Any]]:
    sav = bundle.report.savings
    kpi = bundle.kpi
    pv = bundle.plan_view
    cfg = bundle.settings_snapshot
    route_count = len(bundle.report.utilization)
    avg_cost_route = round(sav.optimized_cost_eur / route_count, 2) if route_count > 0 else None
    avg_cost_order = (
        round(sav.optimized_cost_eur / sav.routed_orders, 2) if sav.routed_orders > 0 else None
    )
    return [
        {"Wskaźnik": "Koszt odniesienia €", "Wartość": sav.baseline_cost_eur},
        {"Wskaźnik": "Koszt zoptymalizowany €", "Wartość": sav.optimized_cost_eur},
        {"Wskaźnik": "Oszczędność €", "Wartość": sav.savings_eur},
        {"Wskaźnik": "Oszczędność %", "Wartość": sav.savings_pct},
        {"Wskaźnik": "Zlecenia na trasie", "Wartość": sav.routed_orders},
        {"Wskaźnik": "Koszt €/km (ustawienia)", "Wartość": cfg.get("cost_per_km")},
        {
            "Wskaźnik": "Łączny dystans planu [km]",
            "Wartość": (
                round(kpi.total_distance_km, 1)
                if kpi is not None and kpi.total_distance_km is not None
                else None
            ),
        },
        {"Wskaźnik": "Średni koszt / trasa €", "Wartość": avg_cost_route},
        {"Wskaźnik": "Średni koszt / zlecenie €", "Wartość": avg_cost_order},
        {"Wskaźnik": "Trasy poniżej progu zapełnienia", "Wartość": pv.below_min_fill_count},
        {"Wskaźnik": "Numer planu", "Wartość": bundle.report.run_id},
        {"Wskaźnik": "Status planu", "Wartość": plan_status_pl(bundle.report.plan_status)},
        {"Wskaźnik": "Uwaga metodologia", "Wartość": sav.note},
    ]


def _rows_fleet_utilization(
    session: Session,
    report: ReportBundle,
    plan_view: PlanView,
) -> list[dict[str, Any]]:
    vehicles = VehicleRepository(session)
    util_by_vehicle = {u.vehicle_code: u for u in report.utilization}
    route_meta = {str(r.get("vehicle")): r for r in plan_view.routes}
    rows: list[dict[str, Any]] = []
    total_km = 0.0
    total_cost = 0.0
    fill_values: list[float] = []
    for code, util in sorted(util_by_vehicle.items()):
        vehicle = vehicles.get_by_code(code)
        meta = route_meta.get(code, {})
        cost_per_km = round(util.cost_eur / util.distance_km, 3) if util.distance_km > 0 else None
        fill_pct = round(util.fill_ratio * 100, 1) if util.fill_ratio is not None else None
        if util.fill_ratio is not None:
            fill_values.append(util.fill_ratio)
        total_km += util.distance_km
        total_cost += util.cost_eur
        rows.append(
            {
                "Pojazd": code,
                "Typ": vehicle.vehicle_type.value if vehicle is not None else "—",
                "Pojemność [kg]": vehicle.weight_capacity_kg if vehicle is not None else None,
                "Waga [kg]": round(util.total_weight_kg, 1),
                "Zapełnienie [%]": fill_pct,
                "Dropy": util.drop_count,
                "Km": round(util.distance_km, 1),
                "Koszt €": round(util.cost_eur, 2),
                "€/km": cost_per_km,
                "Status trasy": meta.get("route_status_pl") or util.route_status,
            }
        )
    avg_fill = round(sum(fill_values) / len(fill_values) * 100, 1) if fill_values else None
    rows.append(
        {
            "Pojazd": "SUMA / ŚREDNIA",
            "Typ": "",
            "Pojemność [kg]": None,
            "Waga [kg]": None,
            "Zapełnienie [%]": avg_fill,
            "Dropy": None,
            "Km": round(total_km, 1),
            "Koszt €": round(total_cost, 2),
            "€/km": round(total_cost / total_km, 3) if total_km > 0 else None,
            "Status trasy": "",
        }
    )
    return rows


def _rows_comparison(comparison: GenerationComparison) -> list[dict[str, Any]]:
    return [
        {
            "Wskaźnik": "Generacja A",
            "Wartość": comparison.label_a,
            "Delta (B-A)": None,
            "Ocena": "",
        },
        {
            "Wskaźnik": "Generacja B",
            "Wartość": comparison.label_b,
            "Delta (B-A)": None,
            "Ocena": "",
        },
        {
            "Wskaźnik": "Pojazdy",
            "Wartość": None,
            "Delta (B-A)": comparison.delta_vehicles,
            "Ocena": _sentiment_pl("vehicles", float(comparison.delta_vehicles)),
        },
        {
            "Wskaźnik": "Dystans [km]",
            "Wartość": None,
            "Delta (B-A)": round(comparison.delta_km, 1),
            "Ocena": _sentiment_pl("km", comparison.delta_km),
        },
        {
            "Wskaźnik": "Śr. zapełnienie [p.p.]",
            "Wartość": None,
            "Delta (B-A)": round(comparison.delta_avg_fill_pct, 1),
            "Ocena": _sentiment_pl("avg_fill_pct", comparison.delta_avg_fill_pct),
        },
        {
            "Wskaźnik": "Koszt [€]",
            "Wartość": None,
            "Delta (B-A)": round(comparison.delta_cost_eur, 2),
            "Ocena": _sentiment_pl("cost_eur", comparison.delta_cost_eur),
        },
        {
            "Wskaźnik": "Oszczędność [€]",
            "Wartość": None,
            "Delta (B-A)": round(comparison.delta_savings_eur, 2),
            "Ocena": _sentiment_pl("savings_eur", comparison.delta_savings_eur),
        },
        {
            "Wskaźnik": "Zlecenia w magazynie",
            "Wartość": None,
            "Delta (B-A)": comparison.delta_staying,
            "Ocena": _sentiment_pl("staying", float(comparison.delta_staying)),
        },
    ]


def _style_worksheet(ws: Any, *, numeric_cols: set[int] | None = None) -> None:
    from openpyxl.styles import Alignment, Font, PatternFill  # type: ignore[import-untyped]
    from openpyxl.utils import get_column_letter  # type: ignore[import-untyped]

    header_fill = PatternFill("solid", fgColor="0F766E")
    header_font = Font(bold=True, color="FFFFFF")
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
    for col_idx, column in enumerate(ws.columns, start=1):
        max_len = 0
        for cell in column:
            if cell.value is not None:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 4, 48)
    if numeric_cols:
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                if cell.column in numeric_cols and isinstance(cell.value, (int, float)):
                    cell.number_format = "0.00" if abs(cell.value) < 1000 else "0.0"


def _build_all_sheets(
    bundle: ReportXlsxBundle,
) -> dict[ReportSheetId, tuple[str, list[dict[str, Any]]]]:
    attention_rows: list[dict[str, Any]] = list(_rows_attention_summary(bundle))
    if attention_rows:
        attention_sheet: list[dict[str, Any]] = [
            *attention_rows,
            {},
            *bundle.attention_orders,
        ]
    else:
        attention_sheet = list(bundle.attention_orders)

    return {
        ReportSheetId.SUMMARY: ("Podsumowanie", _rows_summary(bundle)),
        ReportSheetId.ROUTES: ("Trasy", _rows_routes(bundle)),
        ReportSheetId.ROUTED_ORDERS: ("Zlecenia na trasach", list(bundle.routed_orders)),
        ReportSheetId.WAREHOUSE: ("W magazynie", list(bundle.staying_orders)),
        ReportSheetId.ATTENTION: ("Wymaga uwagi", attention_sheet),
        ReportSheetId.SAVINGS: ("Oszczędności", _rows_savings(bundle)),
        ReportSheetId.FLEET: ("Wykorzystanie floty", list(bundle.fleet_rows)),
        ReportSheetId.COMPARISON: (
            "Porównanie",
            _rows_comparison(bundle.comparison) if bundle.comparison is not None else [],
        ),
    }


def export_report_xlsx(
    bundle: ReportXlsxBundle,
    *,
    selection: ReportExportSelection | None = None,
) -> bytes:
    """Export report to xlsx bytes (pandas stays inside this function)."""
    buffer = BytesIO()
    all_sheets = _build_all_sheets(bundle)
    active = selection.sheets if selection is not None else frozenset(SHEET_ORDER)

    sheets: list[tuple[str, list[dict[str, Any]]]] = []
    for sheet_id in SHEET_ORDER:
        if sheet_id not in active:
            continue
        if sheet_id == ReportSheetId.COMPARISON and bundle.comparison is None:
            continue
        sheet_name, rows = all_sheets[sheet_id]
        sheets.append((sheet_name, rows))

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet_name, rows in sheets:
            frame = pd.DataFrame(rows)
            if frame.empty and sheet_name != "Podsumowanie":
                frame = pd.DataFrame([{"Info": "Brak danych"}])
            frame.to_excel(writer, sheet_name=sheet_name, index=False)
            ws = writer.sheets[sheet_name]
            numeric_cols: set[int] = set()
            if sheet_name == "Trasy":
                numeric_cols = {5, 9, 10, 11, 12}
            elif sheet_name == "Wykorzystanie floty":
                numeric_cols = {4, 5, 6, 7, 8, 9}
            _style_worksheet(ws, numeric_cols=numeric_cols or None)
    return buffer.getvalue()
