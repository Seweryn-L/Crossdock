# Otwarte wejścia od zespołu — status i follow-up

> Cel: jawna lista danych, bez których T2/T3 idą na **placeholderach**.
> Po dostarczeniu — wykonać checklistę na dole (bez przepisywania architektury).
> Plan T2: [`plan_t2_implementacja.md`](plan_t2_implementacja.md).
> Plan T3: [`plan_t3_implementacja.md`](plan_t3_implementacja.md).
> Harmonogram: [`plan_tworzenia_aplikacji.md`](plan_tworzenia_aplikacji.md) (tabela zależności).

**Status ogólny (10.08.2026):** T3 (CP-SAT przydział) startuje na **kg** + flocie placeholder;
API / geolokalizacja od firmy **nie blokują** T3.

---

## Brakujące wejścia (blokują jakość, nie start kodu)

| ID | Wejście | Od kogo | Potrzebne najpóźniej | Co robimy teraz (placeholder) | Co poprawić po dostarczeniu |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **W-01** | Plik Excel marzec–kwiecień + lista braków / instrukcja raportu | **Patryk** | T2 | Fixture e2open `przykładowe_dane_od_firmy.xlsx` podpięty pod import | Pełny okres marzec–kwiecień + lista braków raportu (jeśli inna niż sample) |
| **W-02** | Słownik kolumn raportu od firmy (mapowanie nazw) | **Sandra** | T2 | Mapowanie empiryczne z pliku e2open w `config/excel_column_mapping.json` | Potwierdzenie / korekta oficjalnym słownikiem Sandry |
| **W-03** | Tabela floty (typy, wymiary, palety, ładowność) | **Martyna** | T2 (krytyczne też dla T3) | Seed 14 pojazdów placeholder + baner w UI | Zastąpić seed realnymi pojemnościami |
| **W-04** | Skąd w danych jest (lub będzie) **liczba palet** (FR-004) | **firma / zespół** | T3 | Solver T3 liczy **tylko kg** | Dodać constraint palet gdy kolumna będzie |
| **W-05** | Docelowe pliki fixtures | zespół / repo | T2 | **Oba pliki są w `tests/fixtures/`** | — |
| **W-06** | Wstępne stawki kosztowe (km / typ, doba magazynowania) | **Sandra** | T6 | — (poza T3) | Config stawek pod raporty i FR-022 |
| **W-07** | Scenariusz wzorcowy „dobry plan” | **Patryk** | T8 | — (poza T3) | Testy golden |
