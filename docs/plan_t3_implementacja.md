# Tydzień 3 — Solver część 1: przydział CP-SAT (plan implementacji)

> Daty w harmonogramie: **28.07–3.08.2026** (realizacja startuje później — nadrabianie poślizgu).
> Harmonogram: [`plan_tworzenia_aplikacji.md`](plan_tworzenia_aplikacji.md) — wiersz T3.
> Powiązane: [`otwarte_wejscia_zespolu.md`](otwarte_wejscia_zespolu.md), [`AGENTS.md`](../AGENTS.md).

## Cel tygodnia

**„Realne zlecenia z importu przydzielone do pojazdów; testy niezmienników przechodzą”.**

## Założenia (bez czekania na firmę)

- Pojemność solvera: **kg** (w Excelu e2open są wagi; palet brak — W-04).
- Flota: seed placeholder Martyny (W-03) — baner w UI.
- Jednostka przydziału: całe `Order` (FR-019) — shipmenty nie są osobnymi zmiennymi.
- Dystans / trasy / limit dropów / zatwierdzanie: **T4**, nie T3.
- Zlecenia bez `weight_kg` → `unassigned` + ostrzeżenie (nie zgadywać wagi).

## Definicja ukończenia (DoD)

- Przycisk „Generuj przydział” na `/plans` → solver przez `run.cpu_bound` (limit 30–60 s, stały seed).
- Wynik: `vehicle → [orders]` + lista nieprzydzielonych + % zapełnienia wagowego.
- Prosty podgląd w UI (bez tras, bez zatwierdzania).
- Niezmienniki: pojemności kg, każde zlecenie ≤ 1 pojazd, FR-019 przez model order-level.
- `optimization/` bez I/O; testy pytest + hypothesis.
- Tag opcjonalny: `t3-done`.

## Poza zakresem T3

Routing Solver, mapa, zatwierdzanie planu, koszty km, API e2open, geokoder, edycja palet.

---

## Krok 0 — DTO (pickle-safe)

`crossdock/optimization/dto.py`:

- `SolverOrder`, `SolverVehicle`, `AssignmentRequest`, `AssignmentResult`
- Bez importów z `storage` / `ui` / `pandas` / `httpx`

## Krok 1 — CP-SAT (`optimization/assignment.py`)

- Zmienne `x[o,v]`; pojemność kg; maximize suma przydzielonej wagi (FR-011)
- `unassigned` dozwolone przy przepełnieniu floty
- `time_limit_s` + `seed` z requestu / Settings

## Krok 2 — Storage + service

- Migracja: `assignment_runs` + `assignment_items` (minimalny zapis wyniku)
- `services/planning.py`: DB → DTO → `solve_assignment` → zapis + audyt

## Krok 3 — Testy

- Golden: mały ręczny zestaw 3 zlecenia / 2 pojazdy
- Hypothesis: niezmienniki wyniku (krótki limit czasu w testach)

## Krok 4 — UI `/plans`

- Przycisk, spinner, tabela przydziału, lista nieprzydzielonych
- Wyłącznie `run.cpu_bound` dla solvera

## Krok 5 — Config / docs / weryfikacja

- `solver_time_limit_s`, `solver_seed` w Settings
- Aktualizacja otwartych wejść + walkthrough T3
- `pre-commit` / pytest czyste

## Kolejność dla AI

```text
0 docs planu
→ DTO + CP-SAT
→ migracja + PlanningService
→ testy
→ UI
→ config + weryfikacja
```

## Ryzyka

| Ryzyko | Mitygacja |
|---|---|
| 3 pojazdy placeholder vs ~50 zleceń | `unassigned` OK; można zwiększyć seed floty |
| Brak palet | tylko kg |
| Windows ProcessPool | entry point już przygotowany w T1 |
