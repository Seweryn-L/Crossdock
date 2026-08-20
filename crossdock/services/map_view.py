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
from crossdock.storage.repositories import AssignmentRepository, OrderRepository

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


@dataclass(frozen=True)
class MapPoint:
    latitude: float
    longitude: float
    label: str
    popup_html: str
    kind: str  # depot | drop
    sequence: int | None = None


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


@dataclass(frozen=True)
class MapPlanView:
    run_id: int
    plan_status: str
    depot: MapPoint
    routes: tuple[VehicleMapRoute, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)
    center: tuple[float, float] = (51.176, 4.836)
    zoom: int = 7
    display_name: str | None = None
    created_at: datetime | None = None


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

        # Group sequenced items by vehicle (skip UNASSIGNED / UNROUTED).
        by_vehicle: dict[str, list[Any]] = {}
        for item in items:
            if item.vehicle_code in {"UNASSIGNED", "UNROUTED"}:
                continue
            if item.sequence is None:
                continue
            by_vehicle.setdefault(item.vehicle_code, []).append(item)

        warnings: list[str] = []
        vehicle_routes: list[VehicleMapRoute] = []
        all_lats: list[float] = [depot_lat]
        all_lons: list[float] = [depot_lon]

        for vehicle_code, vehicle_items in sorted(by_vehicle.items()):
            vehicle_items.sort(key=lambda i: i.sequence or 0)
            color = color_for_vehicle(vehicle_code)
            markers: list[MapPoint] = []
            path: list[tuple[float, float]] = [(depot_lat, depot_lon)]
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
                popup = (
                    f"<b>{item.delivery_code}</b><br/>"
                    f"Pojazd: {vehicle_code}<br/>"
                    f"Kolejność: {item.sequence}<br/>"
                    f"Miasto: {city}<br/>"
                    f"Waga: {item.weight_kg:.1f} kg"
                )
                markers.append(
                    MapPoint(
                        latitude=lat,
                        longitude=lon,
                        label=item.delivery_code,
                        popup_html=popup,
                        kind="drop",
                        sequence=item.sequence,
                    )
                )
                path.append((lat, lon))
                all_lats.append(lat)
                all_lons.append(lon)

            if len(path) == 1:
                # Only depot — nothing drawable for this vehicle
                continue
            path.append((depot_lat, depot_lon))
            waypoints = tuple(path)
            meta = routes_meta.get(vehicle_code)
            stored = _parse_polyline_json(meta.polyline_json if meta is not None else None)
            polyline = stored if stored is not None else waypoints
            for lat, lon in polyline:
                all_lats.append(lat)
                all_lons.append(lon)
            vehicle_routes.append(
                VehicleMapRoute(
                    vehicle_code=vehicle_code,
                    color=color,
                    distance_km=meta.distance_km if meta else None,
                    cost_eur=meta.cost_eur if meta else None,
                    route_status=meta.route_status if meta is not None else "proposed",
                    polyline=polyline,
                    markers=tuple(markers),
                    waypoints=waypoints,
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
            warnings=tuple(warnings),
            center=center,
            zoom=7 if len(vehicle_routes) > 1 else 8,
            display_name=run.display_name,
            created_at=run.created_at,
        )

    def build_latest(self) -> MapPlanView | None:
        latest = AssignmentRepository(self._session).get_latest_run()
        if latest is None:
            return None
        return self.build_for_run(latest.id)
