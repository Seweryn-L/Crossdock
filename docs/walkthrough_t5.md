# Tydzień 5 — Walkthrough (mapa tras)

> Plan: [`plan_t5_implementacja.md`](plan_t5_implementacja.md)

## Zrobione

| Element | Status |
|---|---|
| `services/map_view.py` — DTO tras z planu | done |
| UI `/map` — Leaflet (markery, polilinie, popupy, legenda) | done |
| `/plans` → „Pokaż na mapie” (`?run_id=`) | done |
| Testy MapViewService | done |

## Jak sprawdzić

```powershell
uv run alembic upgrade head
uv run crossdock
```

1. Ustawienia → Lokalizacje → Wczytaj seed (jeśli pusto)
2. Zlecenia → wgraj `carrier_load_status1620780.xlsx` (lub inny e2open)
3. Plany → Generuj plan → **Pokaż na mapie**
4. Mapa: depot + kolorowe trasy, kliknij marker → popup

## Uwagi

- Linie proste (haversine); OSRM — stretch T9.
- Bez współrzędnych drop nie pojawia się na mapie (ostrzeżenie).

## Poza T5

Raporty, buforowanie, OSRM.
