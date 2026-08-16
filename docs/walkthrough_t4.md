# Tydzień 4 — Walkthrough (trasy + zatwierdzanie planu)

> Dokument historyczny (stan na koniec T4). Aktualny obraz: [`stan_projektu.md`](stan_projektu.md).
> Plan: [`plan_t4_implementacja.md`](plan_t4_implementacja.md)

## Zrobione

| Element | Status |
|---|---|
| DTO routingu + `optimization/routing.py` (OR-Tools, max drops, min km) | done |
| Migracja `c3d4e5f6a7b8` (plan_status, sequence, assignment_routes) | done |
| `PlanningService.run_plan` / `approve_plan` + audyt | done |
| UI `/plans` — Generuj plan, Zatwierdź, km/koszt, kolejność | done |
| Testy golden + hypothesis + service | done |
| `cost_per_km` w Settings | done |

## Jak sprawdzić

```powershell
uv run alembic upgrade head
uv run crossdock
```

1. Zaloguj się → **Zlecenia** → wgraj Excel (zlecenia z współrzędnymi w słowniku lokalizacji lub lat/lon).
2. **Plany** → **Generuj plan** (solver w osobnym procesie).
3. Sprawdź tabelę tras (km, €) oraz kolejność dropów na zleceniach.
4. **Zatwierdź plan** → statusy zleceń `planned` → `approved`; generowanie zablokowane.

## Uwagi

- Dystans: haversine (linia prosta); mapa Leaflet — T5.
- Limit dropów: `CROSSDOCK_MAX_DROPS_PER_ROUTE` (domyślnie 3).
- Koszt: `CROSSDOCK_COST_PER_KM` (placeholder do W-06).
- Zlecenia bez coords → `UNROUTED` (bez sekwencji).

## Poza T4

Mapa, raporty, buforowanie, OSRM, API e2open.
