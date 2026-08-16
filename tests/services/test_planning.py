"""PlanningService integration tests (assignment + plan + approve)."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import SecretStr
from sqlalchemy.orm import Session

from crossdock.config import Settings
from crossdock.domain.models import Location, Order, OrderStatus, Shipment, Vehicle, VehicleType
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
    )


def _add_vehicle(session: Session, code: str = "T1") -> None:
    VehicleRepository(session).add(
        Vehicle(
            code=code,
            vehicle_type=VehicleType.TRUCK,
            pallet_capacity=20,
            weight_capacity_kg=12000,
            is_placeholder=False,
        )
    )


def _add_order(
    session: Session,
    *,
    code: str,
    weight: float,
    lat: float,
    lon: float,
    city: str = "Paris",
) -> Order:
    loc = Location(name="Hub", city="Antwerp", country="BE", latitude=51.22, longitude=4.40)
    dest = Location(name=f"Cust-{code}", city=city, country="FR", latitude=lat, longitude=lon)
    saved = OrderRepository(session).add_many(
        [
            Order(
                delivery_code=code,
                shipments=[Shipment(shipment_number=f"S-{code}", weight_kg=weight)],
                pickup_location=loc,
                delivery_location=dest,
                delivery_date=date(2026, 8, 1),
                status=OrderStatus.NEW,
            )
        ]
    )
    return saved[0]


def test_planning_service_assigns_and_persists(db_session: Session) -> None:
    _add_vehicle(db_session)
    loc = Location(name="Hub", city="Antwerp", country="BE")
    dest = Location(name="Cust", city="Paris", country="FR")
    for i, w in enumerate([2000.0, 3000.0, 4000.0], start=1):
        OrderRepository(db_session).add_many(
            [
                Order(
                    delivery_code=f"ORD-{i}",
                    shipments=[Shipment(shipment_number=f"S-{i}", weight_kg=w)],
                    pickup_location=loc,
                    delivery_location=dest,
                    delivery_date=date(2026, 8, 1),
                    status=OrderStatus.NEW,
                )
            ]
        )

    outcome = PlanningService(db_session, settings=_settings()).run_assignment(username="tester")
    assert outcome.run_id >= 1
    assert outcome.result.status in {"OPTIMAL", "FEASIBLE"}
    assert len(outcome.result.assigned_order_ids) == 3


def test_run_plan_routes_and_sets_planned(db_session: Session) -> None:
    _add_vehicle(db_session)
    _add_order(db_session, code="A", weight=2000, lat=48.85, lon=2.35, city="Paris")
    _add_order(db_session, code="B", weight=2500, lat=50.85, lon=4.35, city="Brussels")
    _add_order(db_session, code="C", weight=1800, lat=51.92, lon=4.48, city="Rotterdam")

    outcome = PlanningService(db_session, settings=_settings()).run_plan(username="tester")
    assert outcome.run_id >= 1
    assert len(outcome.planned_order_ids) == 3

    for oid in outcome.planned_order_ids:
        order = OrderRepository(db_session).get_by_id(oid)
        assert order is not None
        assert order.status == OrderStatus.PLANNED

    repo = AssignmentRepository(db_session)
    run = repo.get_run(outcome.run_id)
    assert run is not None
    assert run.plan_status == "draft"
    assert run.total_distance_km is not None and run.total_distance_km > 0
    routes = repo.list_routes_for_run(outcome.run_id)
    assert len(routes) == 1
    assert routes[0].drop_count <= 3
    items = repo.list_items_for_run(outcome.run_id)
    sequenced = [i for i in items if i.sequence is not None]
    assert len(sequenced) == 3
    seqs = sorted(i.sequence for i in sequenced if i.sequence is not None)
    assert seqs == [1, 2, 3]


def test_run_plan_trims_fourth_drop(db_session: Session) -> None:
    _add_vehicle(db_session)
    # Four distinct far-apart cities → 4 drops; max 3 → 1 unrouted
    coords = [
        ("A", 48.85, 2.35, "Paris"),
        ("B", 50.85, 4.35, "Brussels"),
        ("C", 51.92, 4.48, "Rotterdam"),
        ("D", 52.52, 13.40, "Berlin"),
    ]
    for code, lat, lon, city in coords:
        _add_order(db_session, code=code, weight=1500, lat=lat, lon=lon, city=city)

    outcome = PlanningService(db_session, settings=_settings()).run_plan(username="tester")
    routed = set(outcome.planned_order_ids)
    assert len(routed) == 3
    items = AssignmentRepository(db_session).list_items_for_run(outcome.run_id)
    unrouted = [i for i in items if i.vehicle_code == "UNROUTED"]
    assert len(unrouted) == 1


def test_approve_plan_sets_approved_and_blocks_second(db_session: Session) -> None:
    _add_vehicle(db_session)
    _add_order(db_session, code="A", weight=2000, lat=48.85, lon=2.35)
    _add_order(db_session, code="B", weight=2000, lat=50.85, lon=4.35)

    service = PlanningService(db_session, settings=_settings())
    plan = service.run_plan(username="tester")
    approved = service.approve_plan(run_id=plan.run_id, username="approver")
    assert len(approved.approved_order_ids) == 2

    for oid in approved.approved_order_ids:
        order = OrderRepository(db_session).get_by_id(oid)
        assert order is not None
        assert order.status == OrderStatus.APPROVED

    run = AssignmentRepository(db_session).get_run(plan.run_id)
    assert run is not None
    assert run.plan_status == "approved"

    vehicles = VehicleRepository(db_session).list_active()
    assert all(v.is_busy for v in vehicles)

    with pytest.raises(ValueError, match="już zatwierdzony"):
        service.approve_plan(run_id=plan.run_id, username="approver")

    with pytest.raises(ValueError, match="Brak (wolnych pojazdów|zleceń)"):
        service.run_plan(username="tester")


def test_unlock_plan_allows_regenerate(db_session: Session) -> None:
    _add_vehicle(db_session)
    _add_order(db_session, code="A", weight=2000, lat=48.85, lon=2.35)
    _add_order(db_session, code="B", weight=2000, lat=50.85, lon=4.35)

    service = PlanningService(db_session, settings=_settings())
    plan = service.run_plan(username="tester")
    service.approve_plan(run_id=plan.run_id, username="approver")

    unlocked = service.unlock_plan(run_id=plan.run_id, username="unlocker")
    assert len(unlocked.reset_order_ids) == 2
    for oid in unlocked.reset_order_ids:
        order = OrderRepository(db_session).get_by_id(oid)
        assert order is not None
        assert order.status == OrderStatus.NEW

    run = AssignmentRepository(db_session).get_run(plan.run_id)
    assert run is not None
    assert run.plan_status == "draft"
    assert all(not v.is_busy for v in VehicleRepository(db_session).list_active())

    again = service.run_plan(username="tester")
    # Living run: same run id after unlock + regenerate.
    assert again.run_id == plan.run_id


def test_approve_route_locks_vehicle_and_second_plan_keeps_approved(
    db_session: Session,
) -> None:
    _add_vehicle(db_session, code="T1")
    _add_vehicle(db_session, code="T2")
    _add_order(db_session, code="A", weight=2000, lat=48.85, lon=2.35)
    _add_order(db_session, code="B", weight=2000, lat=50.85, lon=4.35)
    _add_order(db_session, code="C", weight=1800, lat=51.92, lon=4.48)

    service = PlanningService(db_session, settings=_settings())
    plan = service.run_plan(username="tester")
    routes = AssignmentRepository(db_session).list_routes_for_run(plan.run_id)
    assert len(routes) >= 1
    first = routes[0]
    assert first.vehicle_id is not None

    approved = service.approve_route(
        run_id=plan.run_id, vehicle_id=first.vehicle_id, username="approver"
    )
    assert approved.vehicle_code == first.vehicle_code
    assert len(approved.approved_order_ids) >= 1

    vehicle = VehicleRepository(db_session).get_by_id(first.vehicle_id)
    assert vehicle is not None and vehicle.is_busy

    run = AssignmentRepository(db_session).get_run(plan.run_id)
    assert run is not None
    assert run.plan_status in {"partial", "approved"}

    approved_ids = set(approved.approved_order_ids)
    # Add a leftover NEW order so regenerate has work if pool emptied.
    remaining_new = [
        o
        for o in OrderRepository(db_session).list_all()
        if o.status == OrderStatus.NEW
    ]
    available = VehicleRepository(db_session).list_available()
    if remaining_new and available:
        again = service.run_plan(username="tester")
        assert again.run_id == plan.run_id
        # Approved orders stay APPROVED and their route remains.
        for oid in approved_ids:
            order = OrderRepository(db_session).get_by_id(oid)
            assert order is not None
            assert order.status == OrderStatus.APPROVED
        kept = AssignmentRepository(db_session).get_route(plan.run_id, first.vehicle_id)
        assert kept is not None
        assert kept.route_status == "approved"

    unlocked = service.unlock_route(
        run_id=plan.run_id, vehicle_id=first.vehicle_id, username="unlocker"
    )
    assert set(unlocked.reset_order_ids) == approved_ids
    vehicle2 = VehicleRepository(db_session).get_by_id(first.vehicle_id)
    assert vehicle2 is not None and not vehicle2.is_busy


def test_delete_plan_allows_regenerate(db_session: Session) -> None:
    _add_vehicle(db_session)
    _add_order(db_session, code="A", weight=2000, lat=48.85, lon=2.35)
    _add_order(db_session, code="B", weight=2000, lat=50.85, lon=4.35)

    service = PlanningService(db_session, settings=_settings())
    plan = service.run_plan(username="tester")
    service.approve_plan(run_id=plan.run_id, username="approver")

    deleted = service.delete_plan(run_id=plan.run_id, username="deleter")
    assert len(deleted.reset_order_ids) == 2
    assert AssignmentRepository(db_session).get_run(plan.run_id) is None

    for oid in deleted.reset_order_ids:
        order = OrderRepository(db_session).get_by_id(oid)
        assert order is not None
        assert order.status == OrderStatus.NEW

    again = service.run_plan(username="tester")
    assert len(again.planned_order_ids) >= 1
    run = AssignmentRepository(db_session).get_run(again.run_id)
    assert run is not None
    assert run.plan_status == "draft"


def test_orders_to_solver_uses_cargo_override() -> None:
    from crossdock.services.planning import orders_to_solver

    loc = Location(name="Hub", city="Antwerp", country="BE")
    dest = Location(name="Cust", city="Paris", country="FR")
    with_cargo = Order(
        id=1,
        delivery_code="CARGO",
        shipments=[Shipment(shipment_number="S1", weight_kg=2000)],
        pickup_location=loc,
        delivery_location=dest,
        delivery_date=date(2026, 8, 1),
        kg_per_pallet=500.0,
    )
    plain = Order(
        id=2,
        delivery_code="PLAIN",
        shipments=[Shipment(shipment_number="S2", weight_kg=2000)],
        pickup_location=loc,
        delivery_location=dest,
        delivery_date=date(2026, 8, 1),
    )
    solver_orders, skipped = orders_to_solver([with_cargo, plain])
    assert skipped == []
    by_id = {o.id: o for o in solver_orders}
    assert by_id[1].pallet_count == 4
    assert by_id[2].pallet_count is None
