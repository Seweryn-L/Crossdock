"""Excel adapter for OrderSource — pandas stays inside this module."""

from __future__ import annotations

from collections import defaultdict
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd

from crossdock.domain.models import Order, Shipment
from crossdock.excel_mapping import ExcelColumnMapping
from crossdock.ingest.ports import ImportReport, RowError
from crossdock.ingest.row_mapper import row_to_shipment_and_locations


def _read_dataframe(source: Path | bytes, mapping: ExcelColumnMapping) -> pd.DataFrame:
    header = mapping.header_row - 1  # pandas is 0-based
    kwargs: dict[str, Any] = {"header": header, "dtype": object}
    if mapping.sheet_name:
        kwargs["sheet_name"] = mapping.sheet_name
    if isinstance(source, Path):
        return pd.read_excel(source, engine="openpyxl", **kwargs)
    return pd.read_excel(BytesIO(source), engine="openpyxl", **kwargs)


def _merge_orders(parts: list[Order]) -> Order:
    """Merge single-shipment orders that share a delivery_code (FR-019 unit)."""
    first = parts[0]
    shipments: list[Shipment] = []
    seen: set[str] = set()
    for part in parts:
        for shipment in part.shipments:
            if shipment.shipment_number in seen:
                continue
            seen.add(shipment.shipment_number)
            shipments.append(shipment)
    return first.model_copy(update={"shipments": shipments})


class ExcelOrderSource:
    """Faza 1 OrderSource: Excel file → domain orders + per-row error report."""

    def __init__(
        self,
        mapping: ExcelColumnMapping,
        *,
        default_delivery_days: int = 7,
    ) -> None:
        self._mapping = mapping
        self._default_delivery_days = default_delivery_days

    def load(self, source: Path | bytes) -> ImportReport:
        try:
            frame = _read_dataframe(source, self._mapping)
        except Exception as exc:  # surface as import warning, not crash
            return ImportReport(
                warnings=[f"Nie udało się odczytać pliku Excela: {exc}"],
            )

        # Normalise column names to stripped strings.
        frame.columns = [str(c).strip() for c in frame.columns]

        rejected: list[RowError] = []
        grouped: dict[str, list[Order]] = defaultdict(list)
        # Excel row = header_row + 1 + frame index (0-based).
        excel_row_base = self._mapping.header_row + 1

        for idx, series in frame.iterrows():
            row_number = excel_row_base + int(idx)  # type: ignore[arg-type]
            row = series.to_dict()
            # Skip completely empty rows.
            if all(
                v is None or (isinstance(v, float) and v != v) or str(v).strip() == ""
                for v in row.values()
            ):
                continue
            try:
                order = row_to_shipment_and_locations(
                    row,
                    self._mapping,
                    default_delivery_days=self._default_delivery_days,
                )
            except (ValueError, KeyError, TypeError) as exc:
                rejected.append(RowError(row_number=row_number, message=str(exc)))
                continue
            grouped[order.delivery_code].append(order)

        orders = [_merge_orders(parts) for parts in grouped.values()]
        return ImportReport(orders=orders, rejected=rejected)
