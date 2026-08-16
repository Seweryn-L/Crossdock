"""Tests for reports, pallet edit (FR-021), and warehouse queue (FR-020)."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import SecretStr
from sqlalchemy.orm import Session

from crossdock.config import Settings
from crossdock.domain.models import Location, Order, OrderStatus, Shipment, Vehicle, VehicleType
from crossdock.services.orders import update_approved_pallets
from crossdock.services.planning import PlanningService
from crossdock.services.reports import build_report, export_report_xlsx
from crossdock.services.warehouse_queue import (
    enqueue_many,
    enqueue_order,
    list_enqueue_candidates,
    list_queue,
    move_order,
)
from crossdock.storage.repositories import OrderRepository, VehicleRepository


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
    )


def _seed_plan(session: Session) -> int:
    VehicleRepository(session).add(
        Vehicle(
            code="T1",
            vehicle_type=VehicleType.TRUCK,
            pallet_capacity=10,
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
        OrderRepository(session).add_many(
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
    plan = PlanningService(session, settings=_settings()).run_plan(username="tester")
    PlanningService(session, settings=_settings()).approve_plan(
        run_id=plan.run_id, username="tester"
    )
    return plan.run_id


def test_build_and_export_report(db_session: Session) -> None:
    run_id = _seed_plan(db_session)
    bundle = build_report(db_session, settings=_settings())
    assert bundle is not None
    assert bundle.run_id == run_id
    assert bundle.plan_status == "approved"
    assert len(bundle.utilization) >= 1
    assert bundle.savings.routed_orders >= 2
    assert bundle.savings.baseline_cost_eur >= bundle.savings.optimized_cost_eur
    xlsx = export_report_xlsx(bundle)
    assert xlsx[:2] == b"PK"  # zip/xlsx magic


def test_pallet_update_approved_only(db_session: Session) -> None:
    _seed_plan(db_session)
    approved = OrderRepository(db_session).list_by_status(OrderStatus.APPROVED)
    assert approved
    oid = approved[0].id
    assert oid is not None

    result = update_approved_pallets(db_session, order_id=oid, total_pallets=5, username="tester")
    assert result.new_total == 5
    assert result.order.total_pallets == 5

    # overflow vs capacity 10 — still ok; 15 triggers warning
    overflow = update_approved_pallets(
        db_session, order_id=oid, total_pallets=15, username="tester"
    )
    assert overflow.needs_replan is True
    assert overflow.warning is not None

    # reject non-approved
    hub = Location(name="Hub", city="Antwerp", country="BE", latitude=51.22, longitude=4.40)
    new_order = OrderRepository(db_session).add_many(
        [
            Order(
                delivery_code="NEW1",
                shipments=[Shipment(shipment_number="SN", weight_kg=100)],
                pickup_location=hub,
                delivery_location=Location(
                    name="X", city="Paris", country="FR", latitude=48.8, longitude=2.3
                ),
                delivery_date=date(2026, 8, 1),
                status=OrderStatus.NEW,
            )
        ]
    )[0]
    assert new_order.id is not None
    with pytest.raises(ValueError, match="approved"):
        update_approved_pallets(
            db_session, order_id=new_order.id, total_pallets=1, username="tester"
        )


def test_warehouse_queue_rotate(db_session: Session) -> None:
    hub = Location(name="Hub", city="Antwerp", country="BE")
    dest = Location(name="Cust", city="Paris", country="FR")
    ids: list[int] = []
    for i in range(3):
        saved = OrderRepository(db_session).add_many(
            [
                Order(
                    delivery_code=f"Q{i}",
                    shipments=[Shipment(shipment_number=f"SQ{i}", weight_kg=100)],
                    pickup_location=hub,
                    delivery_location=dest,
                    delivery_date=date(2026, 8, 1),
                    status=OrderStatus.NEW,
                )
            ]
        )[0]
        assert saved.id is not None
        ids.append(saved.id)
        enqueue_order(db_session, order_id=saved.id, username="tester")

    entries = list_queue(db_session)
    assert [e.order_id for e in entries] == ids

    move_order(db_session, order_id=ids[2], direction="up", username="tester")
    entries = list_queue(db_session)
    assert entries[1].order_id == ids[2]
    assert entries[2].order_id == ids[1]


def test_warehouse_enqueue_candidates(db_session: Session) -> None:
    hub = Location(name="Hub", city="Antwerp", country="BE")
    dest = Location(name="Cust", city="Paris", country="FR")

    def _add(code: str, status: OrderStatus) -> int:
        saved = OrderRepository(db_session).add_many(
            [
                Order(
                    delivery_code=code,
                    shipments=[Shipment(shipment_number=f"S-{code}", weight_kg=100)],
                    pickup_location=hub,
                    delivery_location=dest,
                    delivery_date=date(2026, 8, 1),
                    status=status,
                )
            ]
        )[0]
        assert saved.id is not None
        return saved.id

    new_a = _add("NA", OrderStatus.NEW)
    new_b = _add("NB", OrderStatus.NEW)
    _add("PL", OrderStatus.PLANNED)

    candidates = list_enqueue_candidates(db_session)
    assert {c.order_id for c in candidates} == {new_a, new_b}

    enqueue_order(db_session, order_id=new_a, username="tester")
    candidates = list_enqueue_candidates(db_session)
    assert [c.order_id for c in candidates] == [new_b]

    with pytest.raises(ValueError, match="new"):
        enqueue_order(db_session, order_id=_add("AP", OrderStatus.APPROVED), username="tester")


def test_enqueue_many_skips_non_new_and_already_queued(db_session: Session) -> None:
    hub = Location(name="Hub", city="Antwerp", country="BE")
    dest = Location(name="Cust", city="Paris", country="FR")

    def _add(code: str, status: OrderStatus) -> int:
        saved = OrderRepository(db_session).add_many(
            [
                Order(
                    delivery_code=code,
                    shipments=[Shipment(shipment_number=f"S-{code}", weight_kg=100)],
                    pickup_location=hub,
                    delivery_location=dest,
                    delivery_date=date(2026, 8, 1),
                    status=status,
                )
            ]
        )[0]
        assert saved.id is not None
        return saved.id

    a = _add("EA", OrderStatus.NEW)
    b = _add("EB", OrderStatus.NEW)
    planned = _add("EP", OrderStatus.PLANNED)
    enqueue_order(db_session, order_id=a, username="tester")

    added = enqueue_many(db_session, order_ids=[a, b, planned, 99999], username="tester")
    assert added == 1
    assert [e.order_id for e in list_queue(db_session)] == [a, b]
