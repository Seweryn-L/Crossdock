"""Selectable Excel report sections for the report builder."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ReportSheetId(StrEnum):
    SUMMARY = "summary"
    ROUTES = "routes"
    ROUTED_ORDERS = "routed_orders"
    WAREHOUSE = "warehouse"
    ATTENTION = "attention"
    SAVINGS = "savings"
    FLEET = "fleet"
    COMPARISON = "comparison"


SHEET_LABELS_PL: dict[ReportSheetId, str] = {
    ReportSheetId.SUMMARY: "Podsumowanie",
    ReportSheetId.ROUTES: "Trasy",
    ReportSheetId.ROUTED_ORDERS: "Zlecenia na trasach",
    ReportSheetId.WAREHOUSE: "W magazynie",
    ReportSheetId.ATTENTION: "Wymaga uwagi",
    ReportSheetId.SAVINGS: "Oszczędności",
    ReportSheetId.FLEET: "Wykorzystanie floty",
    ReportSheetId.COMPARISON: "Porównanie",
}

SHEET_ORDER: tuple[ReportSheetId, ...] = (
    ReportSheetId.SUMMARY,
    ReportSheetId.ROUTES,
    ReportSheetId.ROUTED_ORDERS,
    ReportSheetId.WAREHOUSE,
    ReportSheetId.ATTENTION,
    ReportSheetId.SAVINGS,
    ReportSheetId.FLEET,
    ReportSheetId.COMPARISON,
)

PRESET_DISPATCHER: frozenset[ReportSheetId] = frozenset(
    {
        ReportSheetId.SUMMARY,
        ReportSheetId.ROUTES,
        ReportSheetId.ROUTED_ORDERS,
        ReportSheetId.WAREHOUSE,
        ReportSheetId.ATTENTION,
    }
)

PRESET_MANAGEMENT: frozenset[ReportSheetId] = frozenset(
    {
        ReportSheetId.SUMMARY,
        ReportSheetId.SAVINGS,
        ReportSheetId.FLEET,
        ReportSheetId.COMPARISON,
    }
)

PRESET_FULL: frozenset[ReportSheetId] = frozenset(SHEET_ORDER)

STORAGE_KEY = "report_sheet_selection"


@dataclass(frozen=True, slots=True)
class ReportExportSelection:
    sheets: frozenset[ReportSheetId]

    def includes(self, sheet_id: ReportSheetId) -> bool:
        return sheet_id in self.sheets

    @classmethod
    def all_available(cls, *, include_comparison: bool = True) -> ReportExportSelection:
        sheets = set(PRESET_FULL)
        if not include_comparison:
            sheets.discard(ReportSheetId.COMPARISON)
        return cls(sheets=frozenset(sheets))

    @classmethod
    def from_preset(
        cls,
        preset: frozenset[ReportSheetId],
        *,
        include_comparison: bool = True,
    ) -> ReportExportSelection:
        sheets = set(preset)
        if not include_comparison:
            sheets.discard(ReportSheetId.COMPARISON)
        return cls(sheets=frozenset(sheets))


def selection_to_storage(selection: ReportExportSelection) -> list[str]:
    return [sheet.value for sheet in SHEET_ORDER if sheet in selection.sheets]


def selection_from_storage(
    raw: object,
    *,
    include_comparison: bool = True,
) -> ReportExportSelection:
    """Parse persisted user selection; unknown ids are ignored."""
    if not isinstance(raw, list) or not raw:
        return ReportExportSelection.all_available(include_comparison=include_comparison)
    known = {item.value for item in ReportSheetId}
    parsed: set[ReportSheetId] = set()
    for entry in raw:
        code = str(entry).strip()
        if code in known:
            parsed.add(ReportSheetId(code))
    if not parsed:
        return ReportExportSelection.all_available(include_comparison=include_comparison)
    if not include_comparison:
        parsed.discard(ReportSheetId.COMPARISON)
    return ReportExportSelection(sheets=frozenset(parsed))
