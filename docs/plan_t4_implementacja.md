# Tydzień 4 — Solver część 2: trasy + plan w UI (plan implementacji)

> Daty w harmonogramie: **4–10.08.2026** (realizacja nadrabia poślizg — kamień milowy demo).
> Harmonogram: [`plan_tworzenia_aplikacji.md`](plan_tworzenia_aplikacji.md) — wiersz T4.
> Fundament T3: [`plan_t3_implementacja.md`](plan_t3_implementacja.md), [`walkthrough_t3.md`](walkthrough_t3.md).
> Powiązane: [`otwarte_wejscia_zespolu.md`](otwarte_wejscia_zespolu.md), [`AGENTS.md`](../AGENTS.md).

## Cel tygodnia

**„Kompletny przepływ end-to-end: Excel → plan → przegląd → zatwierdzenie.”**

Kamień milowy: minimum na demo istnieje.

## Założenia (zablokowane)

- Pipeline sekwencyjny: CP-SAT (T3) → Routing Solver per pojazd (T4).
- Drop = unikalne miejsce rozładunku (lat/lon lub city|country|name); wiele zleceń = jeden drop.
- Limit dropów: `max_drops_per_route` z Settings (domyślnie 3, FR-012) — przycinanie **przed** routingiem.
- Dystans: haversine (`DistanceProvider`); macierz buduje serwis, do solvera idą metry `int`.
- Zlecenia bez coords → ostrzeżenie, bez sekwencji trasy (`unrouted`).
- Statusy: po generacji zroutowane `NEW → PLANNED`; po zatwierdzeniu `PLANNED → APPROVED`.
- Ponowne generowanie zablokowane, gdy najnowszy run ma `plan_status=approved`.
- Koszt: `distance_km * cost_per_km` (placeholder do W-06).
- Mapa Leaflet — **T5**, nie T4.

## Definicja ukończenia (DoD)

- „Generuj plan” na `/plans` → assignment + routing przez `run.cpu_bound`.
- Pojazd → kolejność dropów → km/koszt; lista nieprzydzielonych / unrouted.
- „Zatwierdź plan” + audyt `planning.approve`.
- Niezmienniki: ≤N dropów, FR-019, sekwencje spójne; `optimization/` bez I/O.
- Tag opcjonalny: `t4-done`.

## Poza zakresem T4

Mapa, raporty Sandry, buforowanie FR-022, OSRM, API e2open, ręczna edycja trasy.

---

## Krok 0 — DTO

`crossdock/optimization/dto.py`: `VehicleRoutingInput`, `RoutingRequest`, `VehicleRoute`,
`RoutingResult`, `PlanResult`.

## Krok 1 — Routing Solver

`crossdock/optimization/routing.py`: przycinanie dropów, OR-Tools RoutingModel per pojazd,
depot start/end, minimize km (FR-014).

## Krok 2 — Storage

Migracja: kolumny planu na `assignment_runs`, `sequence`/`drop_key` na items, tabela
`assignment_routes`. Repo: `save_plan_run`, `approve_run`, `get_run_detail`;
`OrderRepository.set_status_many`.

## Krok 3 — PlanningService

`run_plan` / `approve_plan`; audyt `planning.plan` / `planning.approve`.
Settings: `cost_per_km`.

## Krok 4 — Testy

Golden (3 dropy / 4→trim), hypothesis, approve service.

## Krok 5 — UI `/plans`

Generuj plan, Zatwierdź, szczegóły sekwencji, Σ km/€, baner placeholder.

## Kolejność dla AI

```text
0 docs planu
→ DTO + routing + testy solvera
→ migracja + repo
→ PlanningService + testy
→ UI
→ walkthrough + weryfikacja
```

## Ryzyka

| Ryzyko | Mitygacja |
|---|---|
| Brak współrzędnych w Excelu | Słownik lokalizacji + ostrzeżenia unrouted |
| CP-SAT >3 dropy | Przycinanie przed routingiem |
| Stawki Sandry (W-06) | `cost_per_km` placeholder |
