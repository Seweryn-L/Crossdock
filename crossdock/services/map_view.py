"""Build map-ready DTO from a persisted plan run (T5 / FR-016).

Pure presentation data for NiceGUI Leaflet — no solver, no UI imports.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from crossdock.config import Settings, get_settings
from crossdock.domain.attention import attention_reason_pl
from crossdock.services.plan_view import build_plan_view
from crossdock.storage.repositories import AssignmentRepository, OrderRepository
from crossdock.text_pl import route_status_pl

# Stable palette for vehicle polylines / legend.
_VEHICLE_COLORS: tuple[str, ...] = (
    "#e41a1c",
    "#377eb8",
    "#4daf4a",
    "#984ea3",
    "#ff7f00",
    "#a65628",
    "#f781bf",
    "#66c2a5",
    "#fc8d62",
    "#8da0cb",
    "#e78ac3",
    "#a6d854",
    "#ffd92f",
    "#e5c494",
)


def color_for_vehicle(vehicle_code: str) -> str:
    """Deterministic color from vehicle code."""
    idx = sum(ord(c) for c in vehicle_code) % len(_VEHICLE_COLORS)
    return _VEHICLE_COLORS[idx]


def _parse_polyline_json(raw: str | None) -> tuple[tuple[float, float], ...] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(data, list) or len(data) < 2:
        return None
    points: list[tuple[float, float]] = []
    for item in data:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            return None
        points.append((float(item[0]), float(item[1])))
    return tuple(points)


def _alert_html(messages: tuple[str, ...]) -> str:
    if not messages:
        return ""
    parts = "".join(f'<div class="cd-map-alert">⚠ {msg}</div>' for msg in messages)
    return parts + "<br/>"


@dataclass(frozen=True)
class MapPoint:
    latitude: float
    longitude: float
    label: str
    popup_html: str
    kind: str  # depot | drop | problem
    sequence: int | None = None
    has_problem: bool = False
    problem_labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class VehicleMapRoute:
    vehicle_code: str
    color: str
    distance_km: float | None
    cost_eur: float | None
    route_status: str
    # Closed path: depot → drops in sequence → depot (or denser OSRM geometry)
    polyline: tuple[tuple[float, float], ...]
    markers: tuple[MapPoint, ...]
    # Sparse stop path (depot → drops → depot) for direction arrows / legs
    waypoints: tuple[tuple[float, float], ...] = ()
    order_count: int = 0
    cities_summary: str = ""
    tooltip_html: str = ""
    detail_html: str = ""
    departure_hint: str | None = None
    has_problem: bool = False
    problem_labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class MapPlanView:
    run_id: int
    plan_status: str
    depot: MapPoint
    routes: tuple[VehicleMapRoute, ...]
    problem_markers: tuple[MapPoint, ...] = ()
    warnings: tuple[str, ...] = field(default_factory=tuple)
    center: tuple[float, float] = (51.176, 4.836)
    zoom: int = 7
    display_name: str | None = None
    created_at: datetime | None = None
    min_fill_ratio: float = 0.90


class MapViewService:
    def __init__(self, session: Session, *, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()

    def build_for_run(self, run_id: int) -> MapPlanView | None:
        repo = AssignmentRepository(self._session)
        run = repo.get_run(run_id)
        if run is None:
            return None
        items = repo.list_items_for_run(run_id)
        routes_meta = {r.vehicle_code: r for r in repo.list_routes_for_run(run_id)}
        orders = OrderRepository(self._session)
        plan_view = build_plan_view(self._session, self._settings, run_id=run_id)
        route_info = {str(r["vehicle"]): r for r in plan_view.routes}

        depot_lat = self._settings.depot_latitude
        depot_lon = self._settings.depot_longitude
        depot = MapPoint(
            latitude=depot_lat,
            longitude=depot_lon,
            label="Magazyn",
            popup_html=(
                f"<b>Magazyn cross-dock</b><br/>Herentals<br/>{depot_lat:.4f}, {depot_lon:.4f}"
            ),
            kind="depot",
        )

        by_vehicle: dict[str, list[Any]] = {}
        for item in items:
            if item.vehicle_code in {"UNASSIGNED", "UNROUTED"}:
                continue
            if item.sequence is None:
                continue
            by_vehicle.setdefault(item.vehicle_code, []).append(item)

        warnings: list[str] = []
        vehicle_routes: list[VehicleMapRoute] = []
        problem_markers: list[MapPoint] = []
        all_lats: list[float] = [depot_lat]
        all_lons: list[float] = [depot_lon]
        min_fill = plan_view.min_fill_ratio

        unrouted_with_coords = 0
        for item in items:
            if item.vehicle_code != "UNROUTED":
                continue
            order = orders.get_by_id(item.order_id)
            if order is None:
                continue
            lat = order.delivery_location.latitude
            lon = order.delivery_location.longitude
            reason = attention_reason_pl(item.attention_reason)
            if lat is None or lon is None:
                continue
            unrouted_with_coords += 1
            popup = (
                f"<div class='cd-map-alert'>⚠ Wymaga uwagi: {reason}</div>"
                f"<b>{item.delivery_code}</b><br/>"
                f"Zlecenie bez trasy — uzupełnij dane lub wygeneruj ponownie."
            )
            problem_markers.append(
                MapPoint(
                    latitude=lat,
                    longitude=lon,
                    label=item.delivery_code,
                    popup_html=popup,
                    kind="problem",
                    has_problem=True,
                    problem_labels=(reason,),
                )
            )
            all_lats.append(lat)
            all_lons.append(lon)

        for vehicle_code, vehicle_items in sorted(by_vehicle.items()):
            vehicle_items.sort(key=lambda i: i.sequence or 0)
            color = color_for_vehicle(vehicle_code)
            markers: list[MapPoint] = []
            path: list[tuple[float, float]] = [(depot_lat, depot_lon)]
            cities: list[str] = []
            info = route_info.get(vehicle_code, {})
            below_fill = bool(info.get("below_min_fill"))
            min_slack = info.get("min_slack")
            overdue = isinstance(min_slack, int) and min_slack < 0
            route_problems: list[str] = []
            if below_fill:
                fill_pct = info.get("weight_fill_pct")
                pct_txt = f"{fill_pct:.0f}%" if isinstance(fill_pct, (int, float)) else "—"
                route_problems.append(
                    f"Zapełnienie {pct_txt} — poniżej progu {min_fill * 100:.0f}%"
                )
            if overdue:
                route_problems.append("Spóźnione względem terminu wyjazdu")
            elif isinstance(min_slack, int) and min_slack == 0:
                route_problems.append("Ostatni dzień na wysłanie")

            for item in vehicle_items:
                order = orders.get_by_id(item.order_id)
                if order is None:
                    warnings.append(f"{vehicle_code}: brak zlecenia id={item.order_id} w bazie.")
                    continue
                lat = order.delivery_location.latitude
                lon = order.delivery_location.longitude
                if lat is None or lon is None:
                    warnings.append(
                        f"{vehicle_code}: brak współrzędnych dla "
                        f"{item.delivery_code} — pominięto na mapie."
                    )
                    continue
                city = order.delivery_location.city or "—"
                cities.append(city)
                due = order.delivery_date.isoformat() if order.delivery_date else "—"
                drop_alert = ""
                if item.attention_reason:
                    drop_alert = (
                        f'<div class="cd-map-alert">⚠ {attention_reason_pl(item.attention_reason)}'
                        "</div>"
                    )
                popup = (
                    f"{drop_alert}"
                    f"<b>{item.delivery_code}</b><br/>"
                    f"Pojazd: {vehicle_code}<br/>"
                    f"Kolejność: {item.sequence}<br/>"
                    f"Miasto: {city}<br/>"
                    f"Waga: {item.weight_kg:.1f} kg<br/>"
                    f"Termin: {due}"
                )
                markers.append(
                    MapPoint(
                        latitude=lat,
                        longitude=lon,
                        label=item.delivery_code,
                        popup_html=popup,
                        kind="drop",
                        sequence=item.sequence,
                        has_problem=bool(item.attention_reason),
                        problem_labels=(
                            (attention_reason_pl(item.attention_reason),)
                            if item.attention_reason
                            else ()
                        ),
                    )
                )
                path.append((lat, lon))
                all_lats.append(lat)
                all_lons.append(lon)

            if len(path) == 1:
                continue
            path.append((depot_lat, depot_lon))
            waypoints = tuple(path)
            meta = routes_meta.get(vehicle_code)
            stored = _parse_polyline_json(meta.polyline_json if meta is not None else None)
            polyline = stored if stored is not None else waypoints
            for lat, lon in polyline:
                all_lats.append(lat)
                all_lons.append(lon)
            status = meta.route_status if meta is not None else "proposed"
            km = meta.distance_km if meta else None
            cost = meta.cost_eur if meta else None
            unique_cities = list(dict.fromkeys(cities))
            if len(unique_cities) <= 3:
                cities_summary = ", ".join(unique_cities) if unique_cities else "—"
            else:
                cities_summary = ", ".join(unique_cities[:3]) + f"… (+{len(unique_cities) - 3})"
            km_txt = f"{km:.1f} km" if km is not None else "—"
            cost_txt = f"{cost:.0f} €" if cost is not None else "—"
            status_pl = route_status_pl(status)
            drop_lines_parts: list[str] = []
            for m in markers:
                if m.sequence is None:
                    continue
                prefix = "⚠ " if m.has_problem else ""
                drop_lines_parts.append(f"{prefix}{m.sequence}. {m.label}")
            drop_lines = "<br/>".join(drop_lines_parts)
            problem_tuple = tuple(route_problems)
            has_problem = bool(problem_tuple)
            alerts = _alert_html(problem_tuple)
            tooltip_html = (
                f"<b>{vehicle_code}</b> · {status_pl}<br/>"
                f"Dropy: {len(markers)} · zlecenia: {len(markers)}<br/>"
                f"{cities_summary}<br/>"
                f"{km_txt} · {cost_txt}"
            )
            detail_html = (
                f"{alerts}"
                f"<b>{vehicle_code}</b><br/>"
                f"Status: {status_pl}<br/>"
                f"Zlecenia / dropy: {len(markers)}<br/>"
                f"Miasta: {cities_summary}<br/>"
                f"Dystans: {km_txt}<br/>"
                f"Koszt: {cost_txt}<br/>"
                f"<br/><b>Kolejność:</b><br/>{drop_lines or '—'}"
            )
            vehicle_routes.append(
                VehicleMapRoute(
                    vehicle_code=vehicle_code,
                    color=color,
                    distance_km=km,
                    cost_eur=cost,
                    route_status=status,
                    polyline=polyline,
                    markers=tuple(markers),
                    waypoints=waypoints,
                    order_count=len(markers),
                    cities_summary=cities_summary,
                    tooltip_html=tooltip_html,
                    detail_html=detail_html,
                    has_problem=has_problem,
                    problem_labels=problem_tuple,
                )
            )

        center = (
            (min(all_lats) + max(all_lats)) / 2,
            (min(all_lons) + max(all_lons)) / 2,
        )
        return MapPlanView(
            run_id=run.id,
            plan_status=run.plan_status,
            depot=depot,
            routes=tuple(vehicle_routes),
            problem_markers=tuple(problem_markers),
            warnings=tuple(warnings),
            center=center,
            zoom=7 if len(vehicle_routes) > 1 else 8,
            display_name=run.display_name,
            created_at=run.created_at,
            min_fill_ratio=min_fill,
        )

    def build_latest(self) -> MapPlanView | None:
        latest = AssignmentRepository(self._session).get_latest_run()
        if latest is None:
            return None
        return self.build_for_run(latest.id)
