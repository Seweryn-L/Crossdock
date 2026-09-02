"""Tests for generation KPI aggregation."""

from __future__ import annotations

from datetime import date

from pydantic import SecretStr
from sqlalchemy.orm import Session

from crossdock.config import Settings
from crossdock.domain.models import Location, Order, OrderStatus, Shipment, Vehicle, VehicleType
from crossdock.services.generation_compare import compare_generations, delta_sentiment
from crossdock.services.generation_kpi import build_generation_kpi
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


def _seed_vehicle(db_session: Session) -> None:
    VehicleRepository(db_session).add(
        Vehicle(
            code="T1",
            vehicle_type=VehicleType.TRUCK,
            pallet_capacity=10,
            weight_capacity_kg=12_000,
            is_placeholder=False,
        )
    )


def _seed_order(db_session: Session, code: str, *, lat: float = 48.85, lon: float = 2.35) -> None:
    hub = Location(name="Hub", city="Antwerp", country="BE", latitude=51.22, longitude=4.40)
    delivery = Location(
        name=f"C-{code}",
        city="Paris",
        country="FR",
        latitude=lat,
        longitude=lon,
    )
    OrderRepository(db_session).add_many(
        [
            Order(
                delivery_code=code,
                shipments=[Shipment(shipment_number=f"S-{code}", weight_kg=500)],
                pickup_location=hub,
                delivery_location=delivery,
                delivery_date=date(2026, 8, 1),
                status=OrderStatus.NEW,
            )
        ]
    )


def test_build_generation_kpi_after_plan(db_session: Session) -> None:
    cfg = _settings()
    _seed_vehicle(db_session)
    _seed_order(db_session, "A1")
    db_session.commit()
    svc = PlanningService(db_session, settings=cfg)
    outcome = svc.run_plan(username="tester")
    kpi = build_generation_kpi(db_session, run_id=outcome.run_id, settings=cfg)
    assert kpi is not None
    assert kpi.run_id == outcome.run_id
    assert kpi.orders_in_planning == kpi.riding + kpi.staying + kpi.attention
    assert kpi.route_count >= 0


def test_compare_generations_delta(db_session: Session) -> None:
    cfg = _settings()
    _seed_vehicle(db_session)
    _seed_order(db_session, "B1")
    db_session.commit()
    svc = PlanningService(db_session, settings=cfg)
    outcome_a = svc.run_plan(username="tester")
    _seed_order(db_session, "B2")
    db_session.commit()
    outcome_b = svc.run_plan(username="tester")
    cmp = compare_generations(db_session, outcome_a.run_id, outcome_b.run_id, settings=cfg)
    assert cmp is not None
    assert cmp.run_a_id == outcome_a.run_id
    assert cmp.run_b_id == outcome_b.run_id


def test_delta_sentiment_lower_is_better() -> None:
    assert delta_sentiment("km", -10) == "good"
    assert delta_sentiment("km", 10) == "bad"
    assert delta_sentiment("savings_eur", 50) == "good"
