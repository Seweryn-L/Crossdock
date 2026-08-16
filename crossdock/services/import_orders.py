"""Order import use case: Excel → domain orders → SQLite + audit."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from crossdock.config import Settings, effective_planning_date, get_settings
from crossdock.domain.models import Location, Order
from crossdock.excel_mapping import ExcelColumnMapping, load_excel_column_mapping
from crossdock.ingest.excel_import import ExcelOrderSource
from crossdock.ingest.ports import ImportReport, OrderSource, RowError
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


@dataclass(frozen=True)
class SkippedDuplicate:
    delivery_code: str
    existing_order_id: int | None


@dataclass(frozen=True)
class ImportOutcome:
    """Structured persist result for the UI (duplicates listed in full)."""

    accepted_count: int
    skipped: tuple[SkippedDuplicate, ...]
    rejected: tuple[RowError, ...]
    warnings: tuple[str, ...]

    @property
    def skipped_codes(self) -> tuple[str, ...]:
        return tuple(item.delivery_code for item in self.skipped)


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
        as_of = None
        if settings is not None:
            as_of = effective_planning_date(settings)
        elif default_delivery_days is None:
            as_of = effective_planning_date()
        self._source = source or ExcelOrderSource(
            self._mapping,
            default_delivery_days=days,
            as_of=as_of,
        )

    def import_path(self, path: Path, *, username: str) -> ImportOutcome:
        report = self._source.load(path)
        warnings = list(report.warnings)
        to_save = report.orders
        skipped: list[SkippedDuplicate] = []
        if to_save:
            order_repo = OrderRepository(self._session)
            existing_ids = order_repo.existing_delivery_code_ids(
                [order.delivery_code for order in to_save]
            )
            skipped = [
                SkippedDuplicate(
                    delivery_code=order.delivery_code,
                    existing_order_id=existing_ids.get(order.delivery_code),
                )
                for order in to_save
                if order.delivery_code in existing_ids
            ]
            to_save = [order for order in to_save if order.delivery_code not in existing_ids]
        if to_save:
            coords = LocationCoordsRepository(self._session)
            enriched = _enrich_orders(to_save, coords)
            OrderRepository(self._session).add_many(enriched)
            saved_report = ImportReport(
                orders=enriched,
                rejected=report.rejected,
                warnings=warnings,
            )
        else:
            saved_report = ImportReport(
                orders=[],
                rejected=report.rejected,
                warnings=warnings,
            )
        outcome = ImportOutcome(
            accepted_count=saved_report.accepted_count,
            skipped=tuple(skipped),
            rejected=tuple(report.rejected),
            warnings=tuple(warnings),
        )
        AuditLogRepository(self._session).record(
            username=username,
            action="orders.import",
            details={
                "source": str(path),
                "accepted": outcome.accepted_count,
                "rejected": len(outcome.rejected),
                "skipped": len(outcome.skipped),
                "warnings": len(outcome.warnings),
            },
        )
        return outcome
