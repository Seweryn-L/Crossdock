"""Tests for the FR-019 inseparability invariant.

Shipments linked to one order must never be split across vehicles or
warehouse schedules.
"""

from datetime import date

import pytest
from hypothesis import given
from hypothesis import strategies as st

from crossdock.domain.models import (
    DomainError,
    InseparableShipmentsError,
    Location,
    Order,
    Shipment,
    validate_assignment,
)

PICKUP = Location(name="Magazyn Antwerpia")
DELIVERY = Location(name="Odbiorca Bruksela")


def make_order(shipment_numbers: list[str]) -> Order:
    return Order(
        delivery_code="DC-100",
        shipments=[Shipment(shipment_number=n) for n in shipment_numbers],
        pickup_location=PICKUP,
        delivery_location=DELIVERY,
        delivery_date=date(2026, 7, 21),
    )


class TestValidateAssignment:
    def test_same_vehicle_for_all_shipments_is_accepted(self) -> None:
        order = make_order(["S-1", "S-2"])
        validate_assignment(order, {"S-1": "VEH-1", "S-2": "VEH-1"})

    def test_split_across_two_vehicles_is_rejected(self) -> None:
        order = make_order(["S-1", "S-2"])
        with pytest.raises(InseparableShipmentsError):
            validate_assignment(order, {"S-1": "VEH-1", "S-2": "VEH-2"})

    def test_split_across_warehouse_schedules_is_rejected(self) -> None:
        order = make_order(["S-1", "S-2"])
        with pytest.raises(InseparableShipmentsError):
            validate_assignment(order, {"S-1": "WH-MON", "S-2": "WH-WED"})

    def test_single_shipment_order_is_always_valid(self) -> None:
        order = make_order(["S-1"])
        validate_assignment(order, {"S-1": "VEH-7"})

    def test_missing_assignment_for_a_shipment_is_an_error(self) -> None:
        order = make_order(["S-1", "S-2"])
        with pytest.raises(DomainError):
            validate_assignment(order, {"S-1": "VEH-1"})


shipment_numbers_strategy = st.lists(
    st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-", min_size=1, max_size=10),
    min_size=1,
    max_size=3,
    unique=True,
)


class TestInseparabilityProperties:
    @given(numbers=shipment_numbers_strategy, vehicle=st.sampled_from(["V1", "V2", "V3"]))
    def test_uniform_assignment_always_accepted(self, numbers: list[str], vehicle: str) -> None:
        order = make_order(numbers)
        validate_assignment(order, dict.fromkeys(numbers, vehicle))

    @given(numbers=shipment_numbers_strategy, data=st.data())
    def test_any_split_into_more_than_one_group_is_rejected(
        self, numbers: list[str], data: st.DataObject
    ) -> None:
        order = make_order(numbers)
        vehicles = data.draw(
            st.lists(
                st.sampled_from(["V1", "V2", "V3", "V4"]),
                min_size=len(numbers),
                max_size=len(numbers),
            )
        )
        assignment = dict(zip(numbers, vehicles, strict=True))
        if len(set(assignment.values())) > 1:
            with pytest.raises(InseparableShipmentsError):
                validate_assignment(order, assignment)
        else:
            validate_assignment(order, assignment)
