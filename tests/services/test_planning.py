"""PlanningService integration tests (assignment + plan + approve)."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import SecretStr
from sqlalchemy.orm import Session

from crossdock.config import Settings
from crossdock.domain.models import Location, Order, OrderStatus, Shipment, Vehicle, VehicleType
from crossdock.services.planning import PlanningService
from crossdock.services.warehouse_queue import enqueue_order, list_queue, set_held
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


def test_run_plan_caps_drops_as_unassigned(db_session: Session) -> None:
    _add_vehicle(db_session)
    # Four distinct far-apart cities → CP-SAT keeps at most 3 drops.
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
    unassigned = [i for i in items if i.vehicle_code == "UNASSIGNED"]
    unrouted = [i for i in items if i.vehicle_code == "UNROUTED"]
    assert len(unassigned) == 1
    assert unrouted == []


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
    assert run.approved_by == "approver"

    with pytest.raises(ValueError, match="już zatwierdzony"):
        service.approve_plan(run_id=plan.run_id, username="approver")

    with pytest.raises(ValueError, match="wolnych pojazdów"):
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
    assert run.approved_by is None

    again = service.run_plan(username="tester")
    assert again.run_id == plan.run_id
    assert len(again.planned_order_ids) >= 1


def test_prepare_plan_request_does_not_delete_existing_items(db_session: Session) -> None:
    _add_vehicle(db_session)
    _add_order(db_session, code="A", weight=2000, lat=48.85, lon=2.35)
    _add_order(db_session, code="B", weight=2000, lat=50.85, lon=4.35)
    service = PlanningService(db_session, settings=_settings())
    plan = service.run_plan(username="tester")
    before = AssignmentRepository(db_session).list_items_for_run(plan.run_id)
    assert before

    request = service.prepare_plan_request()
    after = AssignmentRepository(db_session).list_items_for_run(plan.run_id)
    assert len(after) == len(before)
    assert request.existing_run_id == plan.run_id
    assert {o.id for o in request.solver_orders} == {item.order_id for item in before}


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


def test_approve_plan_removes_orders_from_queue(db_session: Session) -> None:
    _add_vehicle(db_session)
    a = _add_order(db_session, code="A", weight=2000, lat=48.85, lon=2.35)
    b = _add_order(db_session, code="B", weight=2000, lat=50.85, lon=4.35)
    assert a.id is not None and b.id is not None
    enqueue_order(db_session, order_id=a.id, username="tester")
    enqueue_order(db_session, order_id=b.id, username="tester")

    service = PlanningService(db_session, settings=_settings())
    plan = service.run_plan(username="tester")
    approved = service.approve_plan(run_id=plan.run_id, username="approver")
    queued_ids = {e.order_id for e in list_queue(db_session)}
    for oid in approved.approved_order_ids:
        assert oid not in queued_ids


def test_held_orders_are_excluded_from_plan(db_session: Session) -> None:
    _add_vehicle(db_session)
    held = _add_order(db_session, code="HOLD", weight=2000, lat=48.85, lon=2.35)
    free = _add_order(db_session, code="FREE", weight=2000, lat=50.85, lon=4.35)
    assert held.id is not None and free.id is not None
    enqueue_order(db_session, order_id=held.id, username="tester")
    set_held(db_session, order_id=held.id, held=True, username="tester")

    service = PlanningService(db_session, settings=_settings())
    plan = service.run_plan(username="tester")
    held_after = OrderRepository(db_session).get_by_id(held.id)
    assert held_after is not None
    assert held_after.status == OrderStatus.NEW
    assert held.id not in plan.planned_order_ids
    assert any("Wstrzymane w magazynie" in w for w in plan.plan.warnings)

    set_held(db_session, order_id=held.id, held=False, username="tester")
    again = service.run_plan(username="tester")
    assert held.id in again.planned_order_ids


def test_approve_route_marks_vehicle_busy_and_unlocks(db_session: Session) -> None:
    _add_vehicle(db_session)
    _add_order(db_session, code="A", weight=2000, lat=48.85, lon=2.35)
    _add_order(db_session, code="B", weight=2000, lat=50.85, lon=4.35)

    service = PlanningService(db_session, settings=_settings())
    plan = service.run_plan(username="tester")
    routes = AssignmentRepository(db_session).list_routes_for_run(plan.run_id)
    assert routes
    vehicle_id = routes[0].vehicle_id
    assert vehicle_id is not None

    outcome = service.approve_route(run_id=plan.run_id, vehicle_id=vehicle_id, username="approver")
    assert outcome.vehicle_code == routes[0].vehicle_code
    assert outcome.approved_order_ids
    vehicle = VehicleRepository(db_session).get(vehicle_id)
    assert vehicle is not None
    assert vehicle.is_busy is True
    assert VehicleRepository(db_session).list_available() == []

    run = AssignmentRepository(db_session).get_run(plan.run_id)
    assert run is not None
    assert run.plan_status in {"partial", "approved"}
    refreshed = next(
        r
        for r in AssignmentRepository(db_session).list_routes_for_run(plan.run_id)
        if r.vehicle_id == vehicle_id
    )
    assert refreshed.route_status == "approved"

    unlocked = service.unlock_route(run_id=plan.run_id, vehicle_id=vehicle_id, username="unlocker")
    assert unlocked.vehicle_id == vehicle_id
    vehicle = VehicleRepository(db_session).get(vehicle_id)
    assert vehicle is not None
    assert vehicle.is_busy is False
    assert VehicleRepository(db_session).list_available()


def test_rename_and_list_recent_plans(db_session: Session) -> None:
    _add_vehicle(db_session)
    _add_order(db_session, code="A", weight=2000, lat=48.85, lon=2.35)
    service = PlanningService(db_session, settings=_settings())
    plan = service.run_plan(username="tester")

    listed = service.list_recent_plans()
    assert listed
    assert listed[0].run_id == plan.run_id
    assert listed[0].display_name is None
    assert listed[0].label.startswith("Plan #")
    assert "roboczy" in listed[0].label

    stored = service.rename_plan(
        run_id=plan.run_id, display_name="  Tydzień 12-18.06  ", username="tester"
    )
    assert stored == "Tydzień 12-18.06"
    with pytest.raises(ValueError, match="80"):
        service.rename_plan(run_id=plan.run_id, display_name="x" * 81, username="tester")
    renamed = service.list_recent_plans()[0]
    assert renamed.display_name == "Tydzień 12-18.06"
    assert renamed.label.startswith("Tydzień 12-18.06 · #")
    assert f"#{plan.run_id}" in renamed.label

    cleared = service.rename_plan(run_id=plan.run_id, display_name="   ", username="tester")
    assert cleared is None
    assert service.list_recent_plans()[0].display_name is None


def test_generate_on_approved_creates_new_run(db_session: Session) -> None:
    _add_vehicle(db_session, code="T1")
    _add_order(db_session, code="A", weight=2000, lat=48.85, lon=2.35)
    _add_order(db_session, code="B", weight=2000, lat=50.85, lon=4.35)
    service = PlanningService(db_session, settings=_settings())
    first = service.run_plan(username="tester")
    service.approve_plan(run_id=first.run_id, username="approver")
    approved_items = {
        item.order_id for item in AssignmentRepository(db_session).list_items_for_run(first.run_id)
    }

    _add_vehicle(db_session, code="T2")
    _add_order(db_session, code="C", weight=1800, lat=51.92, lon=4.48)
    second = service.run_plan(username="tester", target_run_id=first.run_id)
    assert second.run_id != first.run_id
    first_after = AssignmentRepository(db_session).get_run(first.run_id)
    assert first_after is not None
    assert first_after.plan_status == "approved"
    assert first_after.display_name is None
    still = {
        item.order_id for item in AssignmentRepository(db_session).list_items_for_run(first.run_id)
    }
    assert still == approved_items


def test_prepare_appends_only_to_target_draft(db_session: Session) -> None:
    _add_vehicle(db_session, code="T1")
    _add_vehicle(db_session, code="T2")
    _add_order(db_session, code="A", weight=2000, lat=48.85, lon=2.35)
    service = PlanningService(db_session, settings=_settings())
    first = service.run_plan(username="tester")
    empty = service.create_empty_plan(username="tester")
    request = service.prepare_plan_request(target_run_id=empty)
    assert request.existing_run_id == empty
    assert {o.delivery_code for o in request.solver_orders} == set()
    request_first = service.prepare_plan_request(target_run_id=first.run_id)
    assert request_first.existing_run_id == first.run_id
    assert any(o.delivery_code == "A" for o in request_first.solver_orders)


def _first_routed_vehicle_id(session: Session, run_id: int) -> int:
    routes = AssignmentRepository(session).list_routes_for_run(run_id)
    assert routes
    vehicle_id = routes[0].vehicle_id
    assert vehicle_id is not None
    return vehicle_id


def test_complete_route_delivers_and_frees_vehicle(db_session: Session) -> None:
    _add_vehicle(db_session)
    order_a = _add_order(db_session, code="A", weight=2000, lat=48.85, lon=2.35)
    order_b = _add_order(db_session, code="B", weight=2000, lat=50.85, lon=4.35)
    service = PlanningService(db_session, settings=_settings())
    plan = service.run_plan(username="tester")
    vehicle_id = _first_routed_vehicle_id(db_session, plan.run_id)

    with pytest.raises(ValueError, match="tylko zatwierdzoną"):
        service.complete_route(run_id=plan.run_id, vehicle_id=vehicle_id, username="ops")

    service.approve_route(run_id=plan.run_id, vehicle_id=vehicle_id, username="approver")
    outcome = service.complete_route(run_id=plan.run_id, vehicle_id=vehicle_id, username="ops")
    assert outcome.vehicle_id == vehicle_id
    assert outcome.delivered_order_ids
    for oid in outcome.delivered_order_ids:
        order = OrderRepository(db_session).get_by_id(oid)
        assert order is not None
        assert order.status == OrderStatus.DELIVERED

    vehicle = VehicleRepository(db_session).get(vehicle_id)
    assert vehicle is not None
    assert vehicle.is_busy is False
    assert VehicleRepository(db_session).list_available()

    route = next(
        r
        for r in AssignmentRepository(db_session).list_routes_for_run(plan.run_id)
        if r.vehicle_id == vehicle_id
    )
    assert route.route_status == "completed"
    assert AssignmentRepository(db_session).get_run(plan.run_id) is not None

    with pytest.raises(ValueError, match="już zrealizowana"):
        service.complete_route(run_id=plan.run_id, vehicle_id=vehicle_id, username="ops")

    request = service.prepare_plan_request()
    solver_ids = {o.id for o in request.solver_orders}
    assert order_a.id not in solver_ids
    assert order_b.id not in solver_ids
    for oid in outcome.delivered_order_ids:
        assert oid not in solver_ids


def test_complete_route_keeps_inseparable_shipments(db_session: Session) -> None:
    _add_vehicle(db_session)
    loc = Location(name="Hub", city="Antwerp", country="BE", latitude=51.22, longitude=4.40)
    dest = Location(name="Cust", city="Paris", country="FR", latitude=48.85, longitude=2.35)
    saved = OrderRepository(db_session).add_many(
        [
            Order(
                delivery_code="PAIR",
                shipments=[
                    Shipment(shipment_number="S-PAIR-1", weight_kg=1500),
                    Shipment(shipment_number="S-PAIR-2", weight_kg=1500),
                ],
                pickup_location=loc,
                delivery_location=dest,
                delivery_date=date(2026, 8, 1),
                status=OrderStatus.NEW,
            )
        ]
    )
    order = saved[0]
    assert order.id is not None
    assert len(order.shipments) == 2

    service = PlanningService(db_session, settings=_settings())
    plan = service.run_plan(username="tester")
    vehicle_id = _first_routed_vehicle_id(db_session, plan.run_id)
    service.approve_route(run_id=plan.run_id, vehicle_id=vehicle_id, username="approver")
    outcome = service.complete_route(run_id=plan.run_id, vehicle_id=vehicle_id, username="ops")
    assert order.id in outcome.delivered_order_ids

    refreshed = OrderRepository(db_session).get_by_id(order.id)
    assert refreshed is not None
    assert refreshed.status == OrderStatus.DELIVERED
    assert len(refreshed.shipments) == 2
    assert {s.shipment_number for s in refreshed.shipments} == {"S-PAIR-1", "S-PAIR-2"}


def test_unlock_and_delete_leave_completed_history(db_session: Session) -> None:
    _add_vehicle(db_session)
    _add_order(db_session, code="A", weight=2000, lat=48.85, lon=2.35)
    service = PlanningService(db_session, settings=_settings())
    plan = service.run_plan(username="tester")
    vehicle_id = _first_routed_vehicle_id(db_session, plan.run_id)
    service.approve_route(run_id=plan.run_id, vehicle_id=vehicle_id, username="approver")
    service.complete_route(run_id=plan.run_id, vehicle_id=vehicle_id, username="ops")

    with pytest.raises(ValueError, match="zrealizowana"):
        service.unlock_route(run_id=plan.run_id, vehicle_id=vehicle_id, username="unlocker")
    with pytest.raises(ValueError, match="zrealizowane"):
        service.unlock_plan(run_id=plan.run_id, username="unlocker")
    with pytest.raises(ValueError, match="zrealizowane"):
        service.delete_plan(run_id=plan.run_id, username="deleter")

    route = next(
        r
        for r in AssignmentRepository(db_session).list_routes_for_run(plan.run_id)
        if r.vehicle_id == vehicle_id
    )
    assert route.route_status == "completed"
    order = OrderRepository(db_session).get_by_id(
        AssignmentRepository(db_session).list_items_for_run(plan.run_id)[0].order_id
    )
    assert order is not None
    assert order.status == OrderStatus.DELIVERED
