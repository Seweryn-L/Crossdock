# Otwarte wejścia od zespołu — status i follow-up

> Cel: jawna lista danych od zespołu. Kod T2–T7 **nie jest zablokowany**.
> Aktualny stan systemu: [`stan_projektu.md`](stan_projektu.md).

**Status ogólny (13.08.2026):** pojemności floty (W-03), szacunek palet warstwowy (W-04) i stawki w Parametrach (W-06) są **DONE**. Solver liczy **kg + palety**. Nadal otwarte: słownik Sandry (W-02), golden Patryka (W-07).

---

## Brakujące wejścia

| ID | Wejście | Od kogo | Potrzebne najpóźniej | Status (13.08.2026) | Co jeszcze |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **W-01** | Excel historyczny + lista braków raportu | **Patryk** / Drive | T2 | **częściowo:** sample e2open + `dane_01.04–31.07.2026.xlsx` + weekly `carrier_load_status` w `dane/` | Pełny okres / lista braków jeśli inna niż sample |
| **W-02** | Słownik kolumn raportu | **Sandra** | T2 | Mapowanie empiryczne w `config/excel_column_mapping.json` | Potwierdzenie oficjalnym słownikiem |
| **W-03** | Tabela floty (typy, palety, kg, liczby) | **Martyna** | T2/T3 | **DONE** — pojemności w `config/fleet_seed.json` + `dane/FLota.xlsx`; liczba sztuk = UI | — |
| **W-04** | Skąd w danych jest **liczba palet** (FR-004) | **firma / zespół** | T3 | **DONE** jako szacunek warstwowy (towar / typ pojazdu / default). Kolumna Excela **nieplanowana**; haczyk w mapowaniu zostaje | — |
| **W-05** | Fixtures | zespół / repo | T2 | **OK** — `tests/fixtures/` | — |
| **W-06** | Stawki kosztowe | **Sandra** | T6 | **DONE** = obecne stawki w Ustawienia → Parametry (`cost_per_km`, magazyn, LTL, próg). Zmiana bez deployu | — |
| **W-07** | Scenariusz „dobry plan” | **Patryk** | T8 | — | Test golden |

---

## Checklist po dostarczeniu

### W-03 flota (Martyna) — pojemności

- [x] `dane/FLota.xlsx` + `config/fleet_seed.json`
- [x] Seed używa realnych palet/kg (bus 8/1050; truck i curtain 33/24500)
- [x] Sync przy starcie aktualizuje stare pojemności w istniejącej DB
- [x] UI Ustawienia → Flota: liczby aktywnych per typ + edytowalne kg/paleta
- [x] Seed 2/4/8 to start, nie cel 130

### W-04 palety — szacunek warstwowy

- [x] Warstwa 1: kg/paleta towaru albo palety na zleceniu (także status „nowe”)
- [x] Warstwa 2: kg/paleta przy typie floty (Ustawienia → Flota)
- [x] Warstwa 3: domyślne kg/paleta towaru (Ustawienia → Parametry) — bufor / kolejka
- [x] CP-SAT sprawdza pallet_capacity + kg
- [x] Tabela Zleceń nie pokazuje jednej liczby „jak bus”
- [x] Plan / raport: palety względem pojazdu na trasie
- [x] Kolumna Excela nieplanowana; haczyk w mapowaniu zostaje

### W-06 stawki

- [x] Jedyny knobs: Ustawienia → Parametry
- [x] Raporty i bufor czytają Settings

### W-01 dane TMS

- [x] Weekly `carrier_load_status *.xlsx` (maj–sierpień 2026) w `dane/`
- [x] `dane_01.04.2026-31.07.2026.xlsx`
- [x] Odświeżony sample firmy w fixtures
- [ ] Lista braków raportu od Patryka (jeśli inna niż sample)

### W-02 / W-07 (otwarte)

- [ ] Oficjalny słownik kolumn Sandry
- [ ] Scenariusz golden
