"""Tests for report export section selection."""

from __future__ import annotations

from crossdock.services.report_export_options import (
    PRESET_DISPATCHER,
    PRESET_MANAGEMENT,
    ReportExportSelection,
    ReportSheetId,
    selection_from_storage,
    selection_to_storage,
)


def test_selection_from_storage_ignores_unknown_ids() -> None:
    sel = selection_from_storage(
        ["summary", "routes", "bogus", "fleet"],
        include_comparison=False,
    )
    assert sel.sheets == frozenset(
        {ReportSheetId.SUMMARY, ReportSheetId.ROUTES, ReportSheetId.FLEET}
    )


def test_selection_from_storage_empty_defaults_to_all() -> None:
    sel = selection_from_storage([], include_comparison=False)
    assert ReportSheetId.COMPARISON not in sel.sheets
    assert ReportSheetId.SUMMARY in sel.sheets
    assert ReportSheetId.ROUTES in sel.sheets


def test_selection_to_storage_preserves_order() -> None:
    sel = ReportExportSelection(
        sheets=frozenset({ReportSheetId.FLEET, ReportSheetId.SUMMARY}),
    )
    assert selection_to_storage(sel) == ["summary", "fleet"]


def test_preset_dispatcher_excludes_fleet() -> None:
    sel = ReportExportSelection.from_preset(PRESET_DISPATCHER, include_comparison=False)
    assert ReportSheetId.FLEET not in sel.sheets
    assert ReportSheetId.ROUTES in sel.sheets


def test_preset_management_includes_fleet_and_comparison() -> None:
    sel = ReportExportSelection.from_preset(PRESET_MANAGEMENT, include_comparison=True)
    assert ReportSheetId.FLEET in sel.sheets
    assert ReportSheetId.COMPARISON in sel.sheets
    assert ReportSheetId.ROUTES not in sel.sheets
