# Tydzień 6 — Raporty + operacje dyspozytorskie (plan implementacji)

> Daty w harmonogramie: **18–24.08.2026**.
> Harmonogram: [`plan_tworzenia_aplikacji.md`](plan_tworzenia_aplikacji.md) — wiersz T6.
> Fundament: T4 (plan + approve), T5 (mapa). Powiązane: FR-017, FR-018, FR-020, FR-021.

## Cel tygodnia

**„Raporty do pobrania; dyspozytor może zmienić palety i rotować kolejkę.”**

## Założenia

- Raport z najnowszego `approved` (fallback: `draft` + ostrzeżenie).
- FR-018: zapełnienie wagowe per pojazd z planu.
- FR-017: baseline 1 zlecenie = 1 pojazd (2× haversine depot–drop × `cost_per_km`); optimized = `total_cost_eur`.
- FR-021: edycja palet tylko dla `approved`; overflow → warning.
- FR-020: ręczna kolejka całych zleceń (`warehouse_queue`).
- Stawki Sandry (W-06): placeholdery.

## DoD

- `/reports` + Excel (2 arkusze)
- Edycja palet + audyt
- `/warehouse` + rotacja + audyt
- Testy + walkthrough

## Poza T6

FR-022, OSRM, API e2open.
