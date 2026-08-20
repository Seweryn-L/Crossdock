"""Tests for human-readable plan view buckets."""

from __future__ import annotations

from datetime import date

from pydantic import SecretStr
from sqlalchemy.orm import Session

from crossdock.config import Settings
from crossdock.domain.models import Location, Order, OrderStatus, Shipment, Vehicle, VehicleType
from crossdock.services.plan_view import (
    REASON_ATTENTION,
    REASON_HOLDING,
    REASON_STAYING,
    build_plan_view,
    classify_item,
)
from crossdock.services.planning import PlanningService
from crossdock.storage.repositories import OrderRepository, VehicleRepository


def _settings(**kwargs: object) -> Settings:
    base = dict(
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
    base.update(kwargs)
    return Settings(**base)  # type: ignore[arg-type]


def _add_vehicle(session: Session, *, weight: float = 12000) -> None:
    VehicleRepository(session).add(
        Vehicle(
            code="T1",
            vehicle_type=VehicleType.TRUCK,
            pallet_capacity=10,
            weight_capacity_kg=weight,
            is_placeholder=False,
        )
    )


def _add_order(
    session: Session,
    *,
    code: str,
    weight: float,
    lat: float | None = 48.85,
    lon: float | None = 2.35,
    city: str = "Paris",
) -> Order:
    hub = Location(name="Hub", city="Antwerp", country="BE", latitude=51.22, longitude=4.40)
    delivery = Location(
        name=f"Cust-{code}",
        city=city,
        country="FR",
        latitude=lat,
        longitude=lon,
    )
    return OrderRepository(session).add_many(
        [
            Order(
                delivery_code=code,
                shipments=[Shipment(shipment_number=f"S-{code}", weight_kg=weight)],
                pickup_location=hub,
                delivery_location=delivery,
                delivery_date=date(2026, 8, 1),
                status=OrderStatus.NEW,
            )
        ]
    )[0]


def test_classify_item_buckets() -> None:
    assert classify_item(vehicle_code="T1", sequence=1) == ("riding", "")
    assert classify_item(vehicle_code="UNASSIGNED", sequence=None) == (
        "staying",
        REASON_STAYING,
    )
    assert classify_item(vehicle_code="UNROUTED", sequence=None) == (
        "attention",
        REASON_ATTENTION,
    )


def test_build_plan_view_riding_and_staying(db_session: Session) -> None:
    # Capacity for ~2 orders of 2000; third stays UNASSIGNED
    _add_vehicle(db_session, weight=4500)
    _add_order(db_session, code="A", weight=2000, lat=48.85, lon=2.35)
    _add_order(db_session, code="B", weight=2000, lat=50.85, lon=4.35)
    _add_order(db_session, code="C", weight=2000, lat=51.92, lon=4.48)

    PlanningService(db_session, settings=_settings()).run_plan(username="tester")
    view = build_plan_view(db_session, settings=_settings())
    assert view.summary is not None
    assert view.summary.riding >= 1
    assert view.summary.staying >= 1
    assert view.summary.riding + view.summary.staying + view.summary.attention == 3
    assert len(view.staying_order_ids) == view.summary.staying
    assert "zostaje w magazynie" in view.summary.to_polish()
    for row in view.staying:
        assert row["reason"] == REASON_STAYING


def test_build_plan_view_extra_city_stays(db_session: Session) -> None:
    _add_vehicle(db_session, weight=12000)
    coords = [
        ("A", 48.85, 2.35, "Paris"),
        ("B", 50.85, 4.35, "Brussels"),
        ("C", 51.92, 4.48, "Rotterdam"),
        ("D", 52.52, 13.40, "Berlin"),
    ]
    for code, lat, lon, city in coords:
        _add_order(db_session, code=code, weight=1500, lat=lat, lon=lon, city=city)

    PlanningService(db_session, settings=_settings(max_drops_per_route=3)).run_plan(
        username="tester"
    )
    view = build_plan_view(db_session, settings=_settings(max_drops_per_route=3))
    assert view.summary is not None
    assert view.summary.riding == 3
    assert view.summary.staying == 1
    assert view.summary.attention == 0
    for row in view.staying:
        assert row["reason"] == REASON_STAYING


def test_build_plan_view_flags_below_min_fill(db_session: Session) -> None:
    _add_vehicle(db_session, weight=12000)
    _add_order(db_session, code="A", weight=1500, lat=48.85, lon=2.35)
    PlanningService(db_session, settings=_settings(min_fill_ratio=0.90)).run_plan(username="tester")
    view = build_plan_view(db_session, settings=_settings(min_fill_ratio=0.90))
    assert view.below_min_fill_count == 1
    assert view.routes
    assert view.routes[0]["below_min_fill"] is True
    assert view.routes[0]["weight_fill_pct"] == round(1500 / 12000 * 100)


def test_thin_route_holds_when_slack_remains(db_session: Session) -> None:
    _add_vehicle(db_session, weight=12000)
    _add_order(db_session, code="A", weight=4800, lat=48.85, lon=2.35)
    settings = _settings(planning_date=date(2026, 7, 25), min_fill_ratio=0.90)
    PlanningService(db_session, settings=settings).run_plan(username="tester")
    view = build_plan_view(db_session, settings=settings)
    assert view.routes
    assert view.routes[0]["disposition"] == "hold"
    assert view.holding_order_ids
    assert view.summary is not None
    assert view.summary.riding == 0
    assert view.staying
    assert view.staying[0]["reason"] == REASON_HOLDING


def test_thin_route_sends_on_last_leave_day(db_session: Session) -> None:
    _add_vehicle(db_session, weight=12000)
    _add_order(db_session, code="A", weight=4800, lat=48.85, lon=2.35)
    settings = _settings(planning_date=date(2026, 7, 30), min_fill_ratio=0.90)
    PlanningService(db_session, settings=settings).run_plan(username="tester")
    view = build_plan_view(db_session, settings=settings)
    assert view.routes[0]["disposition"] == "send"
    assert view.summary is not None
    assert view.summary.riding == 1
    assert view.holding_order_ids == ()


def test_overflow_capacity_flips_hold_to_send(db_session: Session) -> None:
    _add_vehicle(db_session, weight=12000)
    _add_order(db_session, code="A", weight=4800, lat=48.85, lon=2.35)
    settings = _settings(
        planning_date=date(2026, 7, 25),
        min_fill_ratio=0.90,
        warehouse_capacity_kg=1000.0,
    )
    PlanningService(db_session, settings=settings).run_plan(username="tester")
    view = build_plan_view(db_session, settings=settings)
    assert view.routes[0]["disposition"] == "send"
    assert view.routes[0]["sla_label"] == "Sugestia wysłania - brak miejsca w magazynie"
    assert view.routes[0]["deadline_label"]
    assert view.holding_order_ids == ()
