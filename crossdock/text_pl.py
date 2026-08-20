"""Polish display labels shared by UI and services (DB codes stay English)."""

from __future__ import annotations

from datetime import datetime

ORDER_STATUS_PL: dict[str, str] = {
    "new": "nowe",
    "planned": "zaplanowane",
    "approved": "zatwierdzone",
    "delivered": "zrealizowane",
}

PLAN_STATUS_PL: dict[str, str] = {
    "draft": "roboczy",
    "partial": "częściowo zatwierdzony",
    "approved": "zatwierdzony",
}

ROUTE_STATUS_PL: dict[str, str] = {
    "proposed": "propozycja",
    "approved": "zatwierdzona",
    "completed": "zrealizowana",
}

QUEUE_STATUS_PL: dict[str, str] = {
    "waiting": "oczekuje",
    "held": "wstrzymane",
    "available": "dostępne",
}

BUFFER_ACTION_PL: dict[str, str] = {
    "buffer": "przytrzymaj",
    "ship_now": "wyślij teraz",
    "buforuj": "przytrzymaj",
    "wyślij teraz": "wyślij teraz",
}


def order_status_pl(code: str | None) -> str:
    if code is None:
        return "—"
    return ORDER_STATUS_PL.get(str(code), str(code))


def plan_status_pl(code: str | None) -> str:
    if code is None:
        return "—"
    return PLAN_STATUS_PL.get(str(code), str(code))


def route_status_pl(code: str | None) -> str:
    if code is None:
        return "—"
    return ROUTE_STATUS_PL.get(str(code), str(code))


def queue_status_pl(code: str | None) -> str:
    if code is None:
        return "—"
    return QUEUE_STATUS_PL.get(str(code), str(code))


def buffer_action_pl(code: str | None) -> str:
    if code is None:
        return "—"
    return BUFFER_ACTION_PL.get(str(code), str(code))


PLAN_NAME_MAX_LEN = 80

GENERATE_PROTECT_HINT = (
    "Generuj przelicza tylko propozycje i wolną flotę. "
    "Zatwierdzone i zrealizowane trasy pozostają bez zmian."
)
APPROVE_ROUTE_HINT = (
    "Zatwierdzenie blokuje trasę przed kolejnym Generuj: "
    "pojazd jest zajęty, zlecenia przechodzą na „zatwierdzone”."
)
UNLOCK_ROUTE_HINT = (
    "Odblokowanie wraca trasę do propozycji i zlecenia do puli „nowe” "
    "(tylko trasy zatwierdzone, nie zrealizowane)."
)
COMPLETE_ROUTE_HINT = (
    "Zrealizowane zamyka trasę: zlecenia „zrealizowane”, pojazd wolny. "
    "Tego nie da się cofnąć Generuj — tylko historia."
)
DELETE_RUN_HINT = (
    "Usunięcie generacji resetuje tylko nieukończone trasy. "
    "Gdy którakolwiek trasa jest zrealizowana, usuwanie jest zablokowane."
)


def format_plan_label(
    *,
    run_id: int,
    display_name: str | None,
    plan_status: str | None,
    created_at: datetime | None,
) -> str:
    """Dispatcher label: `{name or Generacja} · #{id} · {status} · {dd.mm HH:MM}`."""
    status = plan_status_pl(plan_status)
    stamp = created_at.strftime("%d.%m %H:%M") if created_at is not None else "—"
    name = (display_name or "").strip()
    if name:
        return f"{name} · #{run_id} · {status} · {stamp}"
    return f"Generacja #{run_id} · {status} · {stamp}"
