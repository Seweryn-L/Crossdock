# Tydzień 6 — Walkthrough (raporty + magazyn + palety)

> Plan: [`plan_t6_implementacja.md`](plan_t6_implementacja.md)

## Zrobione

| Element | Status |
|---|---|
| Raporty FR-017/018 + Excel (`/reports`) | done |
| Edycja palet FR-021 (`/orders` → Zmień palety) | done |
| Kolejka magazynowa FR-020 (`/warehouse`) | done |
| Migracja `warehouse_queue` | done (`d4e5f6a7b8c9`) |

## Jak sprawdzić

```powershell
uv run alembic upgrade head
uv run crossdock
```

1. Import + Generuj plan + **Zatwierdź**
2. **Raporty** → podgląd + **Pobierz Excel**
3. **Zlecenia** → zaznacz `approved` → **Zmień palety**
4. **Magazyn** → dodaj ID zlecenia `new` → W górę / W dół

## Uwagi

- Baseline oszczędności: 1 zlecenie = 1 pojazd × `cost_per_km` (W-06 placeholder).
- Overflow palet → warning „wymaga przeplanowania”, bez auto-replan.
