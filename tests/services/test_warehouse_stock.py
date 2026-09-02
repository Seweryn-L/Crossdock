"""Warehouse snapshot and queue integration after route lifecycle."""

from __future__ import annotations

from datetime import date

from pydantic import SecretStr
from sqlalchemy.orm import Session

from crossdock.config import Settings
from crossdock.domain.models import Location, Order, OrderStatus, Shipment, Vehicle, VehicleType
from crossdock.services.planning import PlanningService
from crossdock.services.warehouse_queue import enqueue_order, list_queue
from crossdock.services.warehouse_stock import warehouse_snapshot
from crossdock.storage.repositories import AssignmentRepository, OrderRepository, VehicleRepository


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
        min_fill_ratio=0.90,
        warehouse_capacity_kg=1_000_000.0,
        use_osrm=False,
    )
    base.update(kwargs)
    return Settings(**base)  # type: ignore[arg-type]


def _add_vehicle(session: Session, *, code: str = "T1", weight: float = 12000) -> None:
    VehicleRepository(session).add(
        Vehicle(
            code=code,
            vehicle_type=VehicleType.TRUCK,
            pallet_capacity=20,
            weight_capacity_kg=weight,
            is_placeholder=False,
        )
    )


def _add_order(
    session: Session,
    *,
    code: str,
    weight: float,
    lat: float = 48.85,
    lon: float = 2.35,
    city: str = "Paris",
) -> Order:
    hub = Location(name="Hub", city="Antwerp", country="BE", latitude=51.22, longitude=4.40)
    dest = Location(name=f"Cust-{code}", city=city, country="FR", latitude=lat, longitude=lon)
    return OrderRepository(session).add_many(
        [
            Order(
                delivery_code=code,
                shipments=[Shipment(shipment_number=f"S-{code}", weight_kg=weight)],
                pickup_location=hub,
                delivery_location=dest,
                delivery_date=date(2026, 8, 1),
                status=OrderStatus.NEW,
            )
        ]
    )[0]


def _first_routed_vehicle_id(session: Session, run_id: int) -> int:
    routes = AssignmentRepository(session).list_routes_for_run(run_id)
    assert routes
    vehicle_id = routes[0].vehicle_id
    assert vehicle_id is not None
    return vehicle_id


def _approve_depart(service: PlanningService, run_id: int, vehicle_id: int) -> None:
    service.approve_route(run_id=run_id, vehicle_id=vehicle_id, username="approver")
    service.depart_route(run_id=run_id, vehicle_id=vehicle_id, username="ops")


def test_warehouse_snapshot_includes_approved(db_session: Session) -> None:
    _add_vehicle(db_session)
    _add_order(db_session, code="A", weight=2000, lat=48.85, lon=2.35)
    _add_order(db_session, code="B", weight=2500, lat=50.85, lon=4.35, city="Brussels")
    settings = _settings()
    service = PlanningService(db_session, settings=settings)
    plan = service.run_plan(username="tester")
    vehicle_id = _first_routed_vehicle_id(db_session, plan.run_id)
    before = warehouse_snapshot(db_session, settings=settings, run_id=plan.run_id)
    assert before.used_kg == 4500.0
    service.approve_route(run_id=plan.run_id, vehicle_id=vehicle_id, username="approver")
    after = warehouse_snapshot(db_session, settings=settings, run_id=plan.run_id)
    assert after.used_kg == 4500.0
    assert after.order_count == 2


def test_warehouse_snapshot_excludes_in_transit(db_session: Session) -> None:
    _add_vehicle(db_session)
    _add_order(db_session, code="A", weight=2000, lat=48.85, lon=2.35)
    _add_order(db_session, code="B", weight=2500, lat=50.85, lon=4.35, city="Brussels")
    settings = _settings()
    service = PlanningService(db_session, settings=settings)
    plan = service.run_plan(username="tester")
    vehicle_id = _first_routed_vehicle_id(db_session, plan.run_id)
    _approve_depart(service, plan.run_id, vehicle_id)
    snap = warehouse_snapshot(db_session, settings=settings, run_id=plan.run_id)
    assert snap.used_kg == 0.0
    assert snap.order_count == 0


def test_warehouse_snapshot_excludes_delivered(db_session: Session) -> None:
    _add_vehicle(db_session)
    _add_order(db_session, code="A", weight=2000, lat=48.85, lon=2.35)
    _add_order(db_session, code="B", weight=2500, lat=50.85, lon=4.35, city="Brussels")
    settings = _settings()
    service = PlanningService(db_session, settings=settings)
    plan = service.run_plan(username="tester")
    vehicle_id = _first_routed_vehicle_id(db_session, plan.run_id)
    before = warehouse_snapshot(db_session, settings=settings, run_id=plan.run_id)
    assert before.used_kg == 4500.0
    _approve_depart(service, plan.run_id, vehicle_id)
    service.complete_route(run_id=plan.run_id, vehicle_id=vehicle_id, username="ops")
    after = warehouse_snapshot(db_session, settings=settings, run_id=plan.run_id)
    assert after.used_kg == 0.0
    assert after.order_count == 0


def test_list_queue_skips_delivered(db_session: Session) -> None:
    _add_vehicle(db_session)
    order = _add_order(db_session, code="A", weight=2000)
    assert order.id is not None
    enqueue_order(db_session, order_id=order.id, username="tester")
    OrderRepository(db_session).set_status_many([order.id], OrderStatus.DELIVERED)
    assert list_queue(db_session) == []


def test_complete_route_dequeues_queue(db_session: Session) -> None:
    _add_vehicle(db_session)
    order_a = _add_order(db_session, code="A", weight=2000, lat=48.85, lon=2.35)
    _add_order(db_session, code="B", weight=2500, lat=50.85, lon=4.35, city="Brussels")
    assert order_a.id is not None
    enqueue_order(db_session, order_id=order_a.id, username="tester")
    settings = _settings()
    service = PlanningService(db_session, settings=settings)
    plan = service.run_plan(username="tester")
    vehicle_id = _first_routed_vehicle_id(db_session, plan.run_id)
    _approve_depart(service, plan.run_id, vehicle_id)
    service.complete_route(run_id=plan.run_id, vehicle_id=vehicle_id, username="ops")
    assert list_queue(db_session) == []
