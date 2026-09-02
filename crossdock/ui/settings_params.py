"""Settings parameter metadata for tiered UI (planning / costs / advanced)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ParamTier = Literal["planning", "costs", "advanced"]

TIER_TITLES_PL: dict[ParamTier, str] = {
    "planning": "Planowanie transportu",
    "costs": "Koszty i bufor",
    "advanced": "Zaawansowane",
}


@dataclass(frozen=True, slots=True)
class ParamMeta:
    tier: ParamTier
    label: str
    description: str
    requires_regenerate: bool
    number_format: str = "%.4g"
    is_int: bool = False


PARAM_META: dict[str, ParamMeta] = {
    "min_fill_ratio": ParamMeta(
        tier="planning",
        label="Minimalne zapełnienie",
        description=("Próg, przy którym trasa może zostać wysłana automatycznie (np. 0,90 = 90%)."),
        requires_regenerate=True,
    ),
    "max_drops_per_route": ParamMeta(
        tier="planning",
        label="Maks. punktów rozładunku",
        description="Limit dropów na jedną trasę FTL — wpływa na routing i solver.",
        requires_regenerate=True,
        is_int=True,
    ),
    "ship_lead_days": ParamMeta(
        tier="planning",
        label="Wyprzedzenie wyjazdu [dni]",
        description=(
            "Ile dni przed terminem dostawy pojazd powinien wyjechać (gdy brak daty z importu)."
        ),
        requires_regenerate=True,
        is_int=True,
    ),
    "default_delivery_days": ParamMeta(
        tier="planning",
        label="Domyślny termin dostawy [dni]",
        description="Używany przy imporcie, gdy w Excelu brak daty dostawy.",
        requires_regenerate=True,
        is_int=True,
    ),
    "warehouse_capacity_kg": ParamMeta(
        tier="planning",
        label="Pojemność magazynu [kg]",
        description="Limit masy zleceń czekających na dopełnienie w magazynie.",
        requires_regenerate=True,
    ),
    "planning_date": ParamMeta(
        tier="planning",
        label="Dzień planowania (symulacja)",
        description="Puste pole = dzisiejsza data kalendarzowa. Wpływa na SLA i bufor.",
        requires_regenerate=True,
    ),
    "cost_per_km": ParamMeta(
        tier="costs",
        label="Stawka €/km",
        description="Wpływa na koszt w raportach i na mapie. Nie zmienia przydziału zleceń.",
        requires_regenerate=False,
    ),
    "storage_cost_per_pallet_day": ParamMeta(
        tier="costs",
        label="Koszt magazynu €/paleta/dzień",
        description="Używany przy ocenie opłacalności buforowania zleceń.",
        requires_regenerate=False,
    ),
    "ltl_cost_multiplier": ParamMeta(
        tier="costs",
        label="Mnożnik drobnicy (LTL)",
        description="Szacunek kosztu wysyłki drobnicowej w porównaniu z FTL.",
        requires_regenerate=False,
    ),
    "buffer_savings_threshold": ParamMeta(
        tier="costs",
        label="Próg oszczędności bufora",
        description="Minimalna oszczędność (udział), by zaproponować buforowanie.",
        requires_regenerate=False,
    ),
    "max_buffer_days": ParamMeta(
        tier="costs",
        label="Maks. dni buforowania",
        description="Po ilu dniach oczekiwania system sugeruje wysłanie mimo niskiego zapełnienia.",
        requires_regenerate=False,
        is_int=True,
    ),
    "solver_time_limit_s": ParamMeta(
        tier="advanced",
        label="Limit czasu planowania [s]",
        description="Maksymalny czas pracy solvera CP-SAT i routingu.",
        requires_regenerate=True,
    ),
    "solver_seed": ParamMeta(
        tier="advanced",
        label="Ziarno losowości",
        description="Stałe ziarno zapewnia powtarzalne wyniki przy tych samych danych.",
        requires_regenerate=True,
        is_int=True,
    ),
    "depot_latitude": ParamMeta(
        tier="advanced",
        label="Szerokość geograficzna magazynu",
        description="Punkt startowy tras na mapie i w obliczeniach odległości.",
        requires_regenerate=True,
    ),
    "depot_longitude": ParamMeta(
        tier="advanced",
        label="Długość geograficzna magazynu",
        description="Punkt startowy tras na mapie i w obliczeniach odległości.",
        requires_regenerate=True,
    ),
    "upload_max_mb": ParamMeta(
        tier="advanced",
        label="Limit uploadu Excel [MB]",
        description="Maksymalny rozmiar pliku importu zleceń.",
        requires_regenerate=False,
        is_int=True,
    ),
    "backup_keep": ParamMeta(
        tier="advanced",
        label="Kopie zapasowe — ile trzymać",
        description="Liczba ostatnich kopii bazy danych na dysku.",
        requires_regenerate=False,
        is_int=True,
    ),
    "backup_hour": ParamMeta(
        tier="advanced",
        label="Godzina nocnej kopii",
        description="Godzina automatycznej kopii zapasowej (0-23).",
        requires_regenerate=False,
        is_int=True,
    ),
    "backup_minute": ParamMeta(
        tier="advanced",
        label="Minuta nocnej kopii",
        description="Minuta automatycznej kopii zapasowej (0-59).",
        requires_regenerate=False,
        is_int=True,
    ),
}

TIER_FIELD_ORDER: dict[ParamTier, tuple[str, ...]] = {
    "planning": (
        "min_fill_ratio",
        "max_drops_per_route",
        "ship_lead_days",
        "default_delivery_days",
        "warehouse_capacity_kg",
    ),
    "costs": (
        "cost_per_km",
        "storage_cost_per_pallet_day",
        "ltl_cost_multiplier",
        "buffer_savings_threshold",
        "max_buffer_days",
    ),
    "advanced": (
        "solver_time_limit_s",
        "solver_seed",
        "depot_latitude",
        "depot_longitude",
        "upload_max_mb",
        "backup_keep",
        "backup_hour",
        "backup_minute",
    ),
}

INT_PARAM_KEYS = frozenset(key for key, meta in PARAM_META.items() if meta.is_int)
