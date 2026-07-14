"""Application pages: dashboard and placeholders for upcoming weeks.

UI texts in Polish. Pages become functional in T2-T6; navigation is
clickable from T1 onwards.
"""

from nicegui import ui

from crossdock.ui.layout import page_frame


def _placeholder(title: str, description: str) -> None:
    with page_frame(title), ui.card().classes("w-full max-w-3xl p-8 items-center"):
        ui.icon("construction").classes("text-6xl text-gray-400")
        ui.label(title).classes("text-xl font-bold")
        ui.label("W przygotowaniu").classes("text-sm uppercase text-gray-400")
        ui.label(description).classes("text-gray-600 text-center")


@ui.page("/")
def dashboard_page() -> None:
    with page_frame("Pulpit"):
        with ui.card().classes("w-full max-w-3xl p-6"):
            ui.label("Witaj w systemie Crossdock").classes("text-2xl font-bold")
            ui.label(
                "System optymalizacji cross-dockingu: import zleceń, planowanie "
                "transportów FTL, wizualizacja tras i raporty."
            ).classes("text-gray-600")
        with ui.card().classes("w-full max-w-3xl p-6"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("info").classes("text-blue-500")
                ui.label("Status danych").classes("font-bold")
            ui.label(
                "Brak zaimportowanych zleceń — import Excela będzie dostępny wkrótce."
            ).classes("text-gray-600")


@ui.page("/orders")
def orders_page() -> None:
    _placeholder("Zlecenia", "Lista zleceń transportowych z importu Excela (tydzień 2).")


@ui.page("/plans")
def plans_page() -> None:
    _placeholder("Plany", "Plany transportów FTL wygenerowane przez solver (tygodnie 3-4).")


@ui.page("/map")
def map_page() -> None:
    _placeholder("Mapa", "Wizualizacja tras pojazdów na mapie (tydzień 5).")


@ui.page("/reports")
def reports_page() -> None:
    _placeholder("Raporty", "Raporty zapełnienia pojazdów i oszczędności (tydzień 6).")


@ui.page("/settings")
def settings_page() -> None:
    _placeholder("Ustawienia", "Konfiguracja floty pojazdów i parametrów systemu (tydzień 2).")
