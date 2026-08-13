"""Polish display labels shared by UI and services (DB codes stay English)."""

from __future__ import annotations

ORDER_STATUS_PL: dict[str, str] = {
    "new": "nowe",
    "planned": "zaplanowane",
    "approved": "zatwierdzone",
}

PLAN_STATUS_PL: dict[str, str] = {
    "draft": "roboczy",
    "partial": "częściowo zatwierdzony",
    "approved": "zatwierdzony",
}

ROUTE_STATUS_PL: dict[str, str] = {
    "proposed": "propozycja",
    "approved": "zatwierdzona",
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
