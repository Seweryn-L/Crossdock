# Tydzień 5 — Mapa tras (plan implementacji)

> Daty w harmonogramie: **11–17.08.2026**.
> Harmonogram: [`plan_tworzenia_aplikacji.md`](plan_tworzenia_aplikacji.md) — wiersz T5.
> Fundament T4: [`plan_t4_implementacja.md`](plan_t4_implementacja.md), [`walkthrough_t4.md`](walkthrough_t4.md).
> Powiązane: [`AGENTS.md`](../AGENTS.md), FR-016.

## Cel tygodnia

**„Kliknięcie planu → trasy wszystkich pojazdów widoczne na mapie.”**

## Założenia (zablokowane)

- Leaflet przez NiceGUI `ui.leaflet`; linie proste (haversine), bez OSRM.
- Dane z ostatniego / wybranego `assignment_run`: sequence + lat/lon zleceń + depot z Settings.
- Kolory stałe per `vehicle_code`.
- Brak coords → pomiń punkt + ostrzeżenie (nie crash).

## Definicja ukończenia (DoD)

- `/map` pokazuje depot, dropy, polilinie kolorami, popupy.
- Z `/plans`: „Pokaż na mapie” → `/map?run_id=…`.
- Legenda pojazdów (kod, kolor, km).
- Testy budowy DTO; `optimization/` nietknięte.
- Tag opcjonalny: `t5-done`.

## Poza zakresem T5

OSRM, edycja trasy na mapie, GPS floty, raporty.

---

## Krok 0 — docs

Ten plik + link w harmonogramie.

## Krok 1 — MapViewService + DTO

`crossdock/services/map_view.py`: `MapPoint`, `VehicleMapRoute`, `MapPlanView`.

## Krok 2 — UI `/map`

`ui.leaflet` + legenda + ostrzeżenia.

## Krok 3 — Link z `/plans`

Przycisk „Pokaż na mapie”.

## Krok 4 — Testy + walkthrough

## Kolejność dla AI

```text
0 docs
→ MapViewService + testy
→ UI /map
→ link /plans
→ walkthrough + weryfikacja
```
