"""Excel column mapping loader tests."""

from __future__ import annotations

from pathlib import Path

from crossdock.excel_mapping import load_excel_column_mapping

MAPPING = Path("config/excel_column_mapping.json")


def test_load_mapping_has_required_logical_columns() -> None:
    mapping = load_excel_column_mapping(MAPPING)
    for key in ("delivery_code", "shipment_number", "pickup_name", "delivery_name"):
        assert key in mapping.columns
    assert mapping.header_row >= 1
