# Tydzień 3 — Walkthrough (przydział CP-SAT)

> Dokument historyczny (stan na koniec T3). Aktualny obraz: [`stan_projektu.md`](stan_projektu.md).
> Plan: [`plan_t3_implementacja.md`](plan_t3_implementacja.md)

## Zrobione

| Element | Status |
|---|---|
| `optimization/dto.py` + `assignment.py` (CP-SAT, kg, FR-011/019) | done |
| Migracja `assignment_runs` / `assignment_items` | done (`b2c3d4e5f6a7`) |
| `PlanningService` + audyt | done |
| UI `/plans` — Generuj przydział przez `run.cpu_bound` | done |
| Testy golden + hypothesis | done |
| Seed floty rozszerzony do 14 pojazdów placeholder | done |

## Jak sprawdzić

```powershell
uv run alembic upgrade head
uv run crossdock
```

1. Zaloguj się → **Zlecenia** → wgraj `przykładowe_dane_od_firmy.xlsx`
2. **Plany** → **Generuj przydział**
3. Tabela: pojazd / kod dostawy / waga / zapełnienie; część może być `UNASSIGNED`

## Poza T3

Trasy, limit dropów, zatwierdzanie planu, mapa — T4/T5.
