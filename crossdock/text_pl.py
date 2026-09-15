"""Polish display labels shared by UI and services (DB codes stay English)."""

from __future__ import annotations

from datetime import datetime

ORDER_STATUS_PL: dict[str, str] = {
    "new": "nowe",
    "planned": "zaplanowane",
    "approved": "przypisane do wyjazdu",
    "delivered": "zrealizowane",
}

PLAN_STATUS_PL: dict[str, str] = {
    "draft": "roboczy",
    "partial": "częściowo zatwierdzony",
    "approved": "zatwierdzony",
}

ROUTE_STATUS_PL: dict[str, str] = {
    "proposed": "propozycja",
    "approved": "gotowa do jazdy",
    "in_transit": "w drodze",
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


def attention_reason_pl(code: str | None) -> str:
    from crossdock.domain.attention import attention_reason_pl as _pl

    return _pl(code)


PLAN_NAME_MAX_LEN = 80

GENERATE_PROTECT_HINT = (
    "Generuj przelicza tylko propozycje i wolną flotę. "
    "Zatwierdzone, w drodze i zrealizowane trasy pozostają bez zmian."
)
APPROVE_ROUTE_HINT = (
    "Zatwierdzenie blokuje trasę przed kolejnym Generuj: "
    "pojazd jest zajęty, zlecenia przechodzą na „gotowe do jazdy”."
)
DEPART_ROUTE_HINT = (
    "Oznacza faktyczny wyjazd z magazynu. Trasa przechodzi na „w drodze”; pojazd nadal jest zajęty."
)
UNLOCK_ROUTE_HINT = (
    "Odblokowanie wraca trasę do propozycji i zlecenia do puli „nowe” "
    "(tylko trasy gotowe do jazdy, nie w drodze ani zrealizowane)."
)
COMPLETE_ROUTE_HINT = (
    "Zamyka trasę po powrocie: zlecenia „zrealizowane”, pojazd wolny. "
    "Wymaga wcześniejszego „Wyjechało”. Tego nie da się cofnąć."
)
DELETE_RUN_HINT = (
    "Usunięcie generacji resetuje tylko nieukończone trasy. "
    "Gdy którakolwiek trasa jest zrealizowana, usuwanie jest zablokowane."
)


def route_action_error_pl(exc: Exception, *, vehicle: str | None = None) -> str:
    """Map planning ValueError messages to short dispatcher-facing Polish text."""
    raw = str(exc)
    prefix = f"{vehicle}: " if vehicle else ""
    if "w drodze (najpierw" in raw:
        return f"{prefix}Trasa nie wyjechała — najpierw kliknij „Wyjechało”."
    if "gotowa do jazdy (zatwierdzona)" in raw:
        return f"{prefix}Trasa nie jest gotowa — najpierw „Zatwierdź trasę”."
    if "jest już zrealizowana" in raw:
        return f"{prefix}Trasa już zrealizowana — odśwież widok."
    if "jest już w drodze" in raw:
        return f"{prefix}Trasa już w drodze."
    if "jest już zatwierdzona" in raw:
        return f"{prefix}Trasa już zatwierdzona."
    if "Nie znaleziono trasy" in raw:
        return f"{prefix}Nie znaleziono trasy — odśwież i spróbuj ponownie."
    if "nie istnieje" in raw and "Plan run" in raw:
        return f"{prefix}Brak aktywnego planu — wybierz generację na Planach."
    return f"{prefix}{raw}" if prefix else raw


def format_plan_label(
    *,
    run_id: int,
    display_name: str | None,
    plan_status: str | None,
    created_at: datetime | None,
) -> str:
    """Technical/audit label: `{name or Generacja} · #{id} · {status} · {dd.mm HH:MM}`."""
    status = plan_status_pl(plan_status)
    stamp = created_at.strftime("%d.%m %H:%M") if created_at is not None else "—"
    name = (display_name or "").strip()
    if name:
        return f"{name} · #{run_id} · {status} · {stamp}"
    return f"Generacja #{run_id} · {status} · {stamp}"


def format_plan_summary_title(
    *,
    display_name: str | None,
    plan_status: str | None,
    created_at: datetime | None,
) -> str:
    """Dispatcher-facing summary title without generation id: `{name|status} · {dd.mm HH:MM}`."""
    status = plan_status_pl(plan_status)
    stamp = created_at.strftime("%d.%m %H:%M") if created_at is not None else "—"
    name = (display_name or "").strip()
    if name:
        return f"{name} · {status} · {stamp}"
    return f"{status} · {stamp}"
