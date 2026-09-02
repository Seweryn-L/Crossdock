"""Excel report builder dialog (section selection before download)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from nicegui import app, ui

from crossdock.services.report_export_options import (
    PRESET_DISPATCHER,
    PRESET_FULL,
    PRESET_MANAGEMENT,
    SHEET_LABELS_PL,
    STORAGE_KEY,
    ReportExportSelection,
    ReportSheetId,
    selection_from_storage,
    selection_to_storage,
)

_OPERATIONS_SHEETS: tuple[ReportSheetId, ...] = (
    ReportSheetId.ROUTES,
    ReportSheetId.ROUTED_ORDERS,
    ReportSheetId.WAREHOUSE,
    ReportSheetId.ATTENTION,
)

_FINANCE_SHEETS: tuple[ReportSheetId, ...] = (ReportSheetId.FLEET,)


class ReportBuilderDialog:
    """Dialog with checkboxes and presets for Excel report sections."""

    def __init__(self) -> None:
        self._compare_available = False
        self._checkboxes: dict[ReportSheetId, ui.checkbox] = {}
        self._comparison_hint: ui.label | None = None
        self._on_download: Callable[[ReportExportSelection], Awaitable[None]] | None = None

        self._dialog = ui.dialog()
        with self._dialog, ui.card().classes("p-4 gap-3 min-w-[360px] max-w-[480px]"):
            ui.label("Kreator raportu Excel").classes("text-lg font-medium")
            ui.label("Wybierz sekcje do pliku Excel.").classes("text-sm text-gray-600")

            with ui.row().classes("gap-2 flex-wrap"):
                ui.button(
                    "Pełny",
                    on_click=lambda: self._apply_preset(PRESET_FULL),
                ).props("outline dense no-caps")
                ui.button(
                    "Dyspozytor",
                    on_click=lambda: self._apply_preset(PRESET_DISPATCHER),
                ).props("outline dense no-caps")
                ui.button(
                    "Zarząd",
                    on_click=lambda: self._apply_preset(PRESET_MANAGEMENT),
                ).props("outline dense no-caps")

            with ui.column().classes("gap-1 w-full"):
                ui.label("Wspólne").classes("text-sm font-medium text-gray-700 mt-1")
                self._checkboxes[ReportSheetId.SUMMARY] = ui.checkbox(
                    SHEET_LABELS_PL[ReportSheetId.SUMMARY],
                    value=True,
                ).props('title="Zalecane na pierwszej stronie"')

                ui.label("Operacje").classes("text-sm font-medium text-gray-700 mt-2")
                for sheet_id in _OPERATIONS_SHEETS:
                    self._checkboxes[sheet_id] = ui.checkbox(
                        SHEET_LABELS_PL[sheet_id],
                        value=True,
                    )

                ui.label("Finanse").classes("text-sm font-medium text-gray-700 mt-2")
                for sheet_id in _FINANCE_SHEETS:
                    self._checkboxes[sheet_id] = ui.checkbox(
                        SHEET_LABELS_PL[sheet_id],
                        value=True,
                    )

                ui.label("Opcjonalne").classes("text-sm font-medium text-gray-700 mt-2")
                self._checkboxes[ReportSheetId.COMPARISON] = ui.checkbox(
                    SHEET_LABELS_PL[ReportSheetId.COMPARISON],
                    value=False,
                )
                self._comparison_hint = ui.label(
                    "Zaznacz 2 generacje w historii, aby włączyć porównanie."
                ).classes("text-xs text-gray-500 ml-7")

            with ui.row().classes("gap-2 justify-end w-full mt-2"):
                ui.button("Anuluj", on_click=self._dialog.close).props("flat")
                ui.button("Pobierz", icon="download", on_click=self._confirm).props("color=primary")

    def open(
        self,
        *,
        compare_available: bool,
        on_download: Callable[[ReportExportSelection], Awaitable[None]],
    ) -> None:
        self._compare_available = compare_available
        self._on_download = on_download
        self._load_selection()
        self._update_comparison_state()
        self._dialog.open()

    def _load_selection(self) -> None:
        raw = app.storage.user.get(STORAGE_KEY)
        selection = selection_from_storage(
            raw,
            include_comparison=self._compare_available,
        )
        for sheet_id, checkbox in self._checkboxes.items():
            checkbox.value = sheet_id in selection.sheets

    def _update_comparison_state(self) -> None:
        comparison_cb = self._checkboxes[ReportSheetId.COMPARISON]
        if self._compare_available:
            comparison_cb.enable()
            if self._comparison_hint is not None:
                self._comparison_hint.set_visibility(False)
        else:
            comparison_cb.value = False
            comparison_cb.disable()
            if self._comparison_hint is not None:
                self._comparison_hint.set_visibility(True)

    def _apply_preset(self, preset: frozenset[ReportSheetId]) -> None:
        selection = ReportExportSelection.from_preset(
            preset,
            include_comparison=self._compare_available,
        )
        for sheet_id, checkbox in self._checkboxes.items():
            checkbox.value = sheet_id in selection.sheets

    def _current_selection(self) -> ReportExportSelection:
        selected = {sheet_id for sheet_id, checkbox in self._checkboxes.items() if checkbox.value}
        return ReportExportSelection(sheets=frozenset(selected))

    async def _confirm(self) -> None:
        selection = self._current_selection()
        if not selection.sheets:
            ui.notify("Zaznacz co najmniej jedną sekcję.", type="warning")
            return
        app.storage.user[STORAGE_KEY] = selection_to_storage(selection)
        self._dialog.close()
        if self._on_download is not None:
            await self._on_download(selection)
