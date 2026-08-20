"""Planning-day SLA: hold vs send, overflow, queue priority, same drop."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import SecretStr
from sqlalchemy.orm import Session

from crossdock.config import Settings
from crossdock.domain.models import Location, Order, OrderStatus, Shipment, Vehicle, VehicleType
from crossdock.domain.sla import is_overdue, slack_days
from crossdock.services.plan_view import build_plan_view
from crossdock.services.planning import PlanningService, orders_to_solver
from crossdock.services.warehouse_queue import enqueue_order
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
        planning_date=date(2026, 7, 25),
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
    delivery: date = date(2026, 8, 1),
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
                delivery_date=delivery,
                status=OrderStatus.NEW,
            )
        ]
    )[0]


def test_approve_plan_skips_hold_routes(db_session: Session) -> None:
    _add_vehicle(db_session)
    _add_order(db_session, code="A", weight=4800)
    settings = _settings()
    service = PlanningService(db_session, settings=settings)
    plan = service.run_plan(username="tester")
    view = build_plan_view(db_session, settings=settings, run_id=plan.run_id)
    assert view.routes[0]["disposition"] == "hold"
    with pytest.raises(ValueError, match="dopełnienie"):
        service.approve_plan(run_id=plan.run_id, username="approver")
    order = OrderRepository(db_session).get_by_id(plan.planned_order_ids[0])
    assert order is not None
    assert order.status == OrderStatus.PLANNED


def test_same_drop_joins_waiting_load_on_next_solve(db_session: Session) -> None:
    _add_vehicle(db_session)
    first = _add_order(db_session, code="A", weight=2000)
    settings = _settings()
    service = PlanningService(db_session, settings=settings)
    first_plan = service.run_plan(username="tester")
    view = build_plan_view(db_session, settings=settings, run_id=first_plan.run_id)
    assert view.routes[0]["disposition"] == "hold"
    second = _add_order(db_session, code="B", weight=2000)
    again = service.run_plan(username="tester", target_run_id=first_plan.run_id)
    assert again.run_id == first_plan.run_id
    items = [
        i
        for i in AssignmentRepository(db_session).list_items_for_run(again.run_id)
        if i.vehicle_code not in {"UNASSIGNED", "UNROUTED"}
    ]
    codes = {i.vehicle_code for i in items}
    assert first.id in {i.order_id for i in items}
    assert second.id in {i.order_id for i in items}
    assert len(codes) == 1
    assert len({i.drop_key for i in items}) == 1


def test_overflow_forces_lowest_slack_must_ship(db_session: Session) -> None:
    _add_vehicle(db_session, weight=3000)
    early = _add_order(db_session, code="EARLY", weight=2000, delivery=date(2026, 8, 10))
    due = _add_order(db_session, code="DUE", weight=2000, delivery=date(2026, 8, 1))
    settings = _settings(warehouse_capacity_kg=3000.0)
    service = PlanningService(db_session, settings=settings)
    plan = service.run_plan(username="tester")
    assert due.id in plan.planned_order_ids
    assert early.id not in plan.planned_order_ids
    assert any("Magazyn ponad pojemność" in w for w in plan.plan.warnings)


def test_queue_head_is_treated_as_must_ship(db_session: Session) -> None:
    _add_vehicle(db_session, weight=3000)
    head = _add_order(db_session, code="HEAD", weight=2000)
    heavy = _add_order(db_session, code="HEAVY", weight=2500, lat=50.85, lon=4.35, city="Brussels")
    assert head.id is not None
    enqueue_order(db_session, order_id=head.id, username="tester")
    settings = _settings()
    plan = PlanningService(db_session, settings=settings).run_plan(username="tester")
    assert head.id in plan.planned_order_ids
    assert heavy.id not in plan.planned_order_ids


def test_warehouse_snapshot_counts_new_stock(db_session: Session) -> None:
    _add_order(db_session, code="A", weight=2000)
    _add_order(db_session, code="B", weight=2500)
    settings = _settings(warehouse_capacity_kg=5000.0)
    snap = warehouse_snapshot(db_session, settings=settings)
    assert snap.used_kg == 4500.0
    assert snap.order_count == 2
    assert snap.overflow is False
    assert snap.nearest_must_leave == date(2026, 7, 30)
    assert snap.nearest_slack == 5


def test_warehouse_snapshot_includes_holding_routes(db_session: Session) -> None:
    _add_vehicle(db_session)
    _add_order(db_session, code="A", weight=4800)
    settings = _settings()
    plan = PlanningService(db_session, settings=settings).run_plan(username="tester")
    snap = warehouse_snapshot(db_session, settings=settings, run_id=plan.run_id)
    assert snap.used_kg == 4800.0
    assert snap.order_count == 1


def test_warehouse_snapshot_overflow_flag(db_session: Session) -> None:
    _add_order(db_session, code="A", weight=4000)
    settings = _settings(warehouse_capacity_kg=1000.0)
    snap = warehouse_snapshot(db_session, settings=settings)
    assert snap.overflow is True
    assert snap.fill_ratio > 1.0


def test_orders_to_solver_stamps_overdue_when_past_leave_day() -> None:
    order = Order(
        id=7,
        delivery_code="LATE",
        shipments=[Shipment(shipment_number="S", weight_kg=1000)],
        pickup_location=Location(name="H", city="A", country="BE"),
        delivery_location=Location(name="C", city="P", country="FR"),
        delivery_date=date(2026, 8, 1),
        status=OrderStatus.NEW,
    )
    planning = date(2026, 8, 1)
    slack = slack_days(order.delivery_date, planning, 2)
    assert is_overdue(slack)
    solver, skipped = orders_to_solver([order], planning_date=planning, ship_lead_days=2)
    assert skipped == []
    assert solver[0].must_ship is True
    assert solver[0].overdue is True
    assert solver[0].delivery_date == date(2026, 8, 1)
