# Tydzień 2 — postęp implementacji (start bez danych zespołu)

> Plan: [`plan_t2_implementacja.md`](plan_t2_implementacja.md)
> Braki od zespołu: [`otwarte_wejscia_zespolu.md`](otwarte_wejscia_zespolu.md)

## Zrobione (20.07.2026)

| Krok planu                                                         | Status                                                               |
| ------------------------------------------------------------------ | -------------------------------------------------------------------- |
| 0 Dokumentacja braków                                              | done                                                                 |
| 1 Config mapowania Excela                                          | done — `config/excel_column_mapping.json` (**e2open**, header_row=3) |
| 2 Domain `Vehicle`                                                 | done                                                                 |
| 3 Migracja `vehicles` + `location_coords`, repozytoria, seed floty | done — Alembic `a1b2c3d4e5f6`                                        |
| 4–5 Excel `OrderSource` + `ImportOrdersService` + fixture firmy    | done — `przykładowe_dane_od_firmy.xlsx`                              |
| 6 Haversine `DistanceProvider`                                     | done                                                                 |
| 7 UI `/orders` (upload + AG Grid)                                  | done                                                                 |
| 8 UI `/settings` (flota + baner W-03)                              | done                                                                 |
| 9 Weryfikacja                                                      | pytest / mypy / ruff / import-linter                                 |

Syntetyczny fixture usunięty — import i testy idą wyłącznie na pliku od firmy.

## Jak sprawdzić ręcznie

```powershell
uv sync
uv run alembic upgrade head
uv run crossdock
```

1. Zaloguj się (admin z `.env`).
2. **Zlecenia** — wgraj `tests/fixtures/przykładowe_dane_od_firmy.xlsx`.
3. **Ustawienia** — zobacz 3 pojazdy placeholder + baner o Martynie.

## Świadomie tymczasowe

- Potwierdzenie mapowania kolumn przez Sandrę (W-02) — obecnie empiryczne z pliku
- Pojemności floty (Martyna W-03)
- Brak liczby palet w Excelu (W-04)
- Słownik lokalizacji: tabela gotowa; UI edycji współrzędnych — minimum (enrich przy imporcie)
