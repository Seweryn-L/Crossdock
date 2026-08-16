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
    # No pallet column in company file (W-04).
    assert sample.shipments[0].pallet_count is None


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
        "Drop Plan Date Start": None,
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
        "Drop Plan Date Start": None,
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
        "Drop Plan Date Start": "04/03/2026 00:00",
    }
    with pytest.raises(ValueError, match="kodu dostawy"):
        row_to_shipment_and_locations(row, mapping, default_delivery_days=7)
