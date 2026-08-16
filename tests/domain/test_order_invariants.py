"""Tests for order creation rules, incl. the FR-024 default deadline."""

from datetime import date, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from crossdock.domain.models import Location, Order, OrderStatus, Shipment

PICKUP = Location(name="Magazyn Antwerpia", city="Antwerpen", country="BE")
DELIVERY = Location(name="Odbiorca Gent", city="Gent", country="BE")


def make_order(**kwargs) -> Order:
    defaults = {
        "delivery_code": "DC-001",
        "shipments": [Shipment(shipment_number="S-1")],
        "pickup_location": PICKUP,
        "delivery_location": DELIVERY,
    }
    defaults.update(kwargs)
    return Order.create(**defaults)


class TestDefaultDeliveryDate:
    def test_missing_date_gets_today_plus_seven_days(self) -> None:
        order = make_order()
        assert order.delivery_date == date.today() + timedelta(days=7)

    def test_explicit_date_is_preserved(self) -> None:
        explicit = date(2026, 8, 1)
        order = make_order(delivery_date=explicit)
        assert order.delivery_date == explicit

    def test_default_days_is_configurable(self) -> None:
        order = make_order(default_delivery_days=10)
        assert order.delivery_date == date.today() + timedelta(days=10)

    def test_as_of_overrides_calendar_today(self) -> None:
        as_of = date(2026, 4, 1)
        order = make_order(as_of=as_of, default_delivery_days=7)
        assert order.delivery_date == date(2026, 4, 8)

    @given(days=st.integers(min_value=0, max_value=365))
    def test_default_date_is_always_today_plus_configured_days(self, days: int) -> None:
        order = make_order(default_delivery_days=days)
        assert order.delivery_date == date.today() + timedelta(days=days)


class TestOrderStructure:
    def test_order_requires_at_least_one_shipment(self) -> None:
        with pytest.raises(ValidationError):
            make_order(shipments=[])

    def test_new_order_defaults_to_status_new(self) -> None:
        assert make_order().status == OrderStatus.NEW

    def test_total_pallets_sums_shipments(self) -> None:
        order = make_order(
            shipments=[
                Shipment(shipment_number="S-1", pallet_count=3),
                Shipment(shipment_number="S-2", pallet_count=5),
            ]
        )
        assert order.total_pallets == 8

    def test_total_pallets_is_none_when_any_count_missing(self) -> None:
        order = make_order(
            shipments=[
                Shipment(shipment_number="S-1", pallet_count=3),
                Shipment(shipment_number="S-2"),
            ]
        )
        assert order.total_pallets is None

    def test_total_weight_sums_shipments(self) -> None:
        order = make_order(
            shipments=[
                Shipment(shipment_number="S-1", weight_kg=120.5),
                Shipment(shipment_number="S-2", weight_kg=79.5),
            ]
        )
        assert order.total_weight_kg == pytest.approx(200.0)

    def test_negative_pallets_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Shipment(shipment_number="S-1", pallet_count=-1)
