"""Tests for Excel OrderSource against the real company e2open fixture."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from crossdock.excel_mapping import load_excel_column_mapping
from crossdock.ingest.excel_import import ExcelOrderSource
from crossdock.ingest.row_mapper import row_to_shipment_and_locations
from tests.fixtures.paths import company_orders_fixture

MAPPING = Path("config/excel_column_mapping.json")


@pytest.fixture
def fixture_path() -> Path:
    return company_orders_fixture()


@pytest.fixture
def source() -> ExcelOrderSource:
    mapping = load_excel_column_mapping(MAPPING)
    return ExcelOrderSource(mapping, default_delivery_days=7)


def test_company_file_imports_orders(source: ExcelOrderSource, fixture_path: Path) -> None:
    report = source.load(fixture_path)
    assert report.accepted_count >= 40
    assert len(report.warnings) == 0
    # Sample has one shipment per Order Ref; still must produce valid domain orders.
    sample = report.orders[0]
    assert sample.delivery_code
    assert sample.shipments
    assert sample.pickup_location.name
    assert sample.delivery_location.name
    assert sample.shipments[0].weight_kg is not None
    assert sample.shipments[0].weight_kg > 0
    # No pallet column in the sample file.
    assert sample.shipments[0].pallet_count is None


def test_company_file_imports_must_leave_by_from_pick_end(
    source: ExcelOrderSource, fixture_path: Path
) -> None:
    report = source.load(fixture_path)
    assert report.accepted_count > 0
    sample = report.orders[0]
    assert sample.must_leave_by == date(2026, 3, 31)
    assert sample.delivery_date == date(2026, 4, 3)


def test_company_file_parses_us_dates_and_ids(source: ExcelOrderSource, fixture_path: Path) -> None:
    report = source.load(fixture_path)
    assert report.accepted_count > 0
    # Drop Plan Date Start in fixture is April 2026 range — not FR-024 default.
    assert all(o.delivery_date.year == 2026 for o in report.orders)
    # TMS ID must not become "203893529.0"
    assert all("." not in s.shipment_number for o in report.orders for s in o.shipments)


def test_row_mapper_fr024_when_delivery_date_missing() -> None:
    mapping = load_excel_column_mapping(MAPPING)
    row = {
        "Order Ref": "TEST-REF",
        "TMS ID": 123456,
        "Origin Name": "HUB",
        "Origin City": "Antwerp",
        "Origin Country": "BE",
        "Origin Postal Code": "2000",
        "Destination Name": "CUST",
        "Destination City": "Paris",
        "Destination Country": "FR",
        "Destination Postal Code": "75001",
        "Product Weight": 100,
        "Drop Plan Date End": None,
        "Pick Plan Date End": None,
        "Equipment": "EU: 09 CURTAIN / BOX TRAILER",
    }
    order = row_to_shipment_and_locations(row, mapping, default_delivery_days=7)
    assert order.delivery_date == date.today() + timedelta(days=7)
    assert order.shipments[0].shipment_number == "123456"


def test_row_mapper_fr024_uses_as_of_not_calendar_today() -> None:
    mapping = load_excel_column_mapping(MAPPING)
    row = {
        "Order Ref": "TEST-REF-ASOF",
        "TMS ID": 123456,
        "Origin Name": "HUB",
        "Origin City": "Antwerp",
        "Origin Country": "BE",
        "Origin Postal Code": "2000",
        "Destination Name": "CUST",
        "Destination City": "Paris",
        "Destination Country": "FR",
        "Destination Postal Code": "75001",
        "Product Weight": 100,
        "Drop Plan Date End": None,
        "Pick Plan Date End": None,
        "Equipment": "EU: 09 CURTAIN / BOX TRAILER",
    }
    as_of = date(2026, 4, 1)
    order = row_to_shipment_and_locations(row, mapping, default_delivery_days=7, as_of=as_of)
    assert order.delivery_date == date(2026, 4, 8)


def test_row_mapper_rejects_missing_order_ref() -> None:
    mapping = load_excel_column_mapping(MAPPING)
    row = {
        "Order Ref": "",
        "TMS ID": 1,
        "Origin Name": "A",
        "Destination Name": "B",
        "Product Weight": 1,
        "Drop Plan Date End": "04/03/2026 00:00",
        "Pick Plan Date End": "03/31/2026 00:00",
    }
    with pytest.raises(ValueError, match="kodu dostawy"):
        row_to_shipment_and_locations(row, mapping, default_delivery_days=7)


def test_row_mapper_splits_comma_separated_order_refs() -> None:
    mapping = load_excel_column_mapping(MAPPING)
    row = {
        "Order Ref": "0853028197,0853028202,0853028204,0853028198",
        "TMS ID": 204694077,
        "Origin Name": "HUB",
        "Origin City": "Antwerp",
        "Origin Country": "BE",
        "Origin Postal Code": "2000",
        "Destination Name": "CUST",
        "Destination City": "Paris",
        "Destination Country": "FR",
        "Destination Postal Code": "75001",
        "Product Weight": "100,200,300,400",
        "Drop Plan Date End": "04/03/2026 00:00",
        "Pick Plan Date End": "03/31/2026 00:00",
        "Equipment": "EU: 09 CURTAIN / BOX TRAILER",
    }
    order = row_to_shipment_and_locations(row, mapping, default_delivery_days=7)
    assert order.delivery_code == "0853028197,0853028202,0853028204,0853028198"
    assert len(order.shipments) == 4
    assert order.shipments[0].shipment_number == "0853028197"
    assert order.shipments[1].shipment_number == "0853028202"
    assert order.shipments[0].weight_kg == 100
    assert order.shipments[3].weight_kg == 400


def test_row_mapper_multi_sku_weight_stays_single_shipment() -> None:
    mapping = load_excel_column_mapping(MAPPING)
    row = {
        "Order Ref": "0853008906",
        "TMS ID": 204208660,
        "Origin Name": "HUB",
        "Origin City": "Antwerp",
        "Origin Country": "BE",
        "Origin Postal Code": "2000",
        "Destination Name": "CUST",
        "Destination City": "Paris",
        "Destination Country": "FR",
        "Destination Postal Code": "75001",
        "Product Weight": "252.5,116.0,450.0",
        "Drop Plan Date End": "04/03/2026 00:00",
        "Pick Plan Date End": "03/31/2026 00:00",
        "Equipment": "EU: 09 CURTAIN / BOX TRAILER",
    }
    order = row_to_shipment_and_locations(row, mapping, default_delivery_days=7)
    assert len(order.shipments) == 1
    assert order.shipments[0].shipment_number == "204208660"
    assert order.shipments[0].weight_kg == pytest.approx(818.5)


def test_company_file_splits_multi_ref_row(source: ExcelOrderSource, fixture_path: Path) -> None:
    report = source.load(fixture_path)
    multi = next(o for o in report.orders if o.delivery_code == "0853012347,0853012331")
    assert len(multi.shipments) == 2
    assert multi.shipments[0].shipment_number == "0853012347"
    assert multi.shipments[1].shipment_number == "0853012331"
