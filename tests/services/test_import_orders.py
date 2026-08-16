"""Tests for ImportOrdersService persistence + audit (company fixture)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from crossdock.excel_mapping import load_excel_column_mapping
from crossdock.services.import_orders import ImportOrdersService
from crossdock.storage.repositories import OrderRepository
from crossdock.storage.tables import AuditLogRow
from tests.fixtures.paths import company_orders_fixture

MAPPING = Path("config/excel_column_mapping.json")


def test_import_orders_service_persists_company_file(db_session: Session) -> None:
    fixture = company_orders_fixture()
    mapping = load_excel_column_mapping(MAPPING)
    service = ImportOrdersService(db_session, mapping=mapping, default_delivery_days=7)
    report = service.import_path(fixture, username="tester")
    assert report.accepted_count >= 40
    assert OrderRepository(db_session).count() == report.accepted_count
    audits = db_session.scalars(
        select(AuditLogRow).where(AuditLogRow.action == "orders.import")
    ).all()
    assert len(audits) == 1


def test_reimport_skips_existing_delivery_codes(db_session: Session) -> None:
    fixture = company_orders_fixture()
    mapping = load_excel_column_mapping(MAPPING)
    service = ImportOrdersService(db_session, mapping=mapping, default_delivery_days=7)
    first = service.import_path(fixture, username="tester")
    count_after_first = OrderRepository(db_session).count()
    assert count_after_first == first.accepted_count
    second = service.import_path(fixture, username="tester")
    assert second.accepted_count == 0
    assert OrderRepository(db_session).count() == count_after_first
    assert len(second.skipped_codes) == count_after_first
    assert len(second.skipped_codes) > 10
    assert not any("…" in msg and "już w bazie" in msg for msg in second.warnings)
    assert {item.delivery_code for item in second.skipped} == set(second.skipped_codes)
    assert all(item.existing_order_id is not None for item in second.skipped)
