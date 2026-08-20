"""Tests for MapViewService (T5)."""

from __future__ import annotations

import json
from datetime import date

from pydantic import SecretStr
from sqlalchemy.orm import Session

from crossdock.config import Settings
from crossdock.domain.models import Location, Order, OrderStatus, Shipment, Vehicle, VehicleType
from crossdock.services.map_view import MapViewService, color_for_vehicle
from crossdock.services.planning import PlanningService
from crossdock.storage.repositories import AssignmentRepository, OrderRepository, VehicleRepository


def _settings() -> Settings:
    return Settings(
        storage_secret=SecretStr("test-secret-not-for-production"),
        solver_time_limit_s=5.0,
        solver_seed=42,
        max_drops_per_route=3,
        cost_per_km=1.2,
        depot_latitude=51.176,
        depot_longitude=4.836,
        planning_date=date(2026, 7, 30),
        ship_lead_days=2,
        warehouse_capacity_kg=1_000_000.0,
        use_osrm=False,
    )


def test_color_for_vehicle_stable() -> None:
    assert color_for_vehicle("T1") == color_for_vehicle("T1")
    assert isinstance(color_for_vehicle("TRUCK-A"), str)


def test_map_view_builds_polyline_in_sequence(db_session: Session) -> None:
    VehicleRepository(db_session).add(
        Vehicle(
            code="T1",
            vehicle_type=VehicleType.TRUCK,
            pallet_capacity=20,
            weight_capacity_kg=12000,
            is_placeholder=False,
        )
    )
    hub = Location(name="Hub", city="Antwerp", country="BE", latitude=51.22, longitude=4.40)
    for code, lat, lon, city in [
        ("A", 48.85, 2.35, "Paris"),
        ("B", 50.85, 4.35, "Brussels"),
        ("C", 51.92, 4.48, "Rotterdam"),
    ]:
        OrderRepository(db_session).add_many(
            [
                Order(
                    delivery_code=code,
                    shipments=[Shipment(shipment_number=f"S-{code}", weight_kg=2000)],
                    pickup_location=hub,
                    delivery_location=Location(
                        name=f"Cust-{code}", city=city, country="FR", latitude=lat, longitude=lon
                    ),
                    delivery_date=date(2026, 8, 1),
                    status=OrderStatus.NEW,
                )
            ]
        )

    plan = PlanningService(db_session, settings=_settings()).run_plan(username="tester")
    view = MapViewService(db_session, settings=_settings()).build_for_run(plan.run_id)
    assert view is not None
    assert view.run_id == plan.run_id
    assert view.depot.kind == "depot"
    assert len(view.routes) >= 1
    route = view.routes[0]
    # Closed path without stored OSRM geometry: depot + N drops + depot
    assert len(route.polyline) == len(route.markers) + 2
    assert route.polyline[0] == route.polyline[-1]
    assert route.polyline[0] == (51.176, 4.836)
    assert route.tooltip_html
    assert route.detail_html
    assert "T1" in route.tooltip_html or route.vehicle_code in route.tooltip_html
    assert route.order_count >= 1
    assert len(route.markers) == 3
    assert route.waypoints == route.polyline
    assert all(m.sequence is not None for m in route.markers)
    assert view.depot.label == "Magazyn"


def test_map_view_prefers_stored_osrm_polyline(db_session: Session) -> None:
    VehicleRepository(db_session).add(
        Vehicle(
            code="T1",
            vehicle_type=VehicleType.TRUCK,
            pallet_capacity=20,
            weight_capacity_kg=12000,
            is_placeholder=False,
        )
    )
    hub = Location(name="Hub", city="Antwerp", country="BE", latitude=51.22, longitude=4.40)
    OrderRepository(db_session).add_many(
        [
            Order(
                delivery_code="A",
                shipments=[Shipment(shipment_number="S-A", weight_kg=2000)],
                pickup_location=hub,
                delivery_location=Location(
                    name="Cust-A", city="Brussels", country="BE", latitude=50.85, longitude=4.35
                ),
                delivery_date=date(2026, 8, 1),
                status=OrderStatus.NEW,
            )
        ]
    )
    plan = PlanningService(db_session, settings=_settings()).run_plan(username="tester")
    repo = AssignmentRepository(db_session)
    routes = repo.list_routes_for_run(plan.run_id)
    assert routes
    dense = [
        [51.176, 4.836],
        [51.10, 4.70],
        [50.95, 4.50],
        [50.85, 4.35],
        [51.176, 4.836],
    ]
    routes[0].polyline_json = json.dumps(dense)
    db_session.flush()

    view = MapViewService(db_session, settings=_settings()).build_for_run(plan.run_id)
    assert view is not None
    route = view.routes[0]
    assert len(route.polyline) == 5
    assert route.polyline[2] == (50.95, 4.50)
    assert len(route.markers) == 1


def test_map_view_skips_missing_coords(db_session: Session) -> None:
    VehicleRepository(db_session).add(
        Vehicle(
            code="T1",
            vehicle_type=VehicleType.TRUCK,
            pallet_capacity=20,
            weight_capacity_kg=12000,
            is_placeholder=False,
        )
    )
    hub = Location(name="Hub", city="Antwerp", country="BE", latitude=51.22, longitude=4.40)
    OrderRepository(db_session).add_many(
        [
            Order(
                delivery_code="WITH",
                shipments=[Shipment(shipment_number="S1", weight_kg=1000)],
                pickup_location=hub,
                delivery_location=Location(
                    name="Paris", city="Paris", country="FR", latitude=48.85, longitude=2.35
                ),
                delivery_date=date(2026, 8, 1),
                status=OrderStatus.NEW,
            ),
            Order(
                delivery_code="WITHOUT",
                shipments=[Shipment(shipment_number="S2", weight_kg=1000)],
                pickup_location=hub,
                delivery_location=Location(name="Unknown", city="Nowhere", country="XX"),
                delivery_date=date(2026, 8, 1),
                status=OrderStatus.NEW,
            ),
        ]
    )
    plan = PlanningService(db_session, settings=_settings()).run_plan(username="tester")
    view = MapViewService(db_session, settings=_settings()).build_for_run(plan.run_id)
    assert view is not None
    labels = {m.label for r in view.routes for m in r.markers}
    assert "WITH" in labels
    assert "WITHOUT" not in labels


def test_map_view_latest_none_when_empty(db_session: Session) -> None:
    assert MapViewService(db_session, settings=_settings()).build_latest() is None
