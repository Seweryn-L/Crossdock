"""Order import use case: Excel → domain orders → SQLite + audit."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from crossdock.config import Settings, get_settings
from crossdock.domain.models import Location, Order
from crossdock.excel_mapping import ExcelColumnMapping, load_excel_column_mapping
from crossdock.ingest.excel_import import ExcelOrderSource
from crossdock.ingest.ports import ImportReport, OrderSource
from crossdock.storage.repositories import (
    AuditLogRepository,
    LocationCoordsRepository,
    OrderRepository,
)


def _enrich_location(location: Location, coords: LocationCoordsRepository) -> Location:
    if location.latitude is not None and location.longitude is not None:
        return location
    known = coords.get(location.location_key())
    if known is None:
        known = coords.find_by_city_country(location.city, location.country)
    if known is None:
        return location
    return location.model_copy(update={"latitude": known.latitude, "longitude": known.longitude})


def _enrich_orders(orders: list[Order], coords: LocationCoordsRepository) -> list[Order]:
    enriched: list[Order] = []
    for order in orders:
        enriched.append(
            order.model_copy(
                update={
                    "pickup_location": _enrich_location(order.pickup_location, coords),
                    "delivery_location": _enrich_location(order.delivery_location, coords),
                }
            )
        )
    return enriched


class ImportOrdersService:
    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        mapping: ExcelColumnMapping | None = None,
        source: OrderSource | None = None,
        default_delivery_days: int | None = None,
    ) -> None:
        self._session = session
        # Avoid requiring .env when mapping/source are injected (unit tests).
        self._settings = settings
        if mapping is not None:
            self._mapping = mapping
        elif settings is not None:
            self._mapping = load_excel_column_mapping(settings.excel_mapping_path)
        else:
            self._mapping = load_excel_column_mapping(get_settings().excel_mapping_path)
        days = default_delivery_days
        if days is None:
            days = (
                settings.default_delivery_days
                if settings is not None
                else get_settings().default_delivery_days
            )
        self._source = source or ExcelOrderSource(
            self._mapping,
            default_delivery_days=days,
        )

    def import_path(self, path: Path, *, username: str) -> ImportReport:
        report = self._source.load(path)
        if report.orders:
            coords = LocationCoordsRepository(self._session)
            enriched = _enrich_orders(report.orders, coords)
            OrderRepository(self._session).add_many(enriched)
            report = ImportReport(
                orders=enriched,
                rejected=report.rejected,
                warnings=report.warnings,
            )
        AuditLogRepository(self._session).record(
            username=username,
            action="orders.import",
            details={
                "source": str(path),
                "accepted": report.accepted_count,
                "rejected": len(report.rejected),
                "warnings": len(report.warnings),
            },
        )
        return report
