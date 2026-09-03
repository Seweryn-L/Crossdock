# Prompt: raporty, koszty, Operacje i generacje — poprawki produktowe

## Dla kogo i po co

**Odbiorca:** developer / agent AI w projekcie Crossdock.

**Cel:** Dopasować raporty, koszty floty, layout Operacji oraz model „generacji” do codziennej pracy dyspozytora. Wyciąć sztuczne „oszczędności”, uprościć komunikaty i sprawić, by **nowa generacja była niezależną alternatywną ścieżką** z pełną flotą.

> To są poprawki do istniejącej aplikacji — nie budujemy od zera.

---

## Zakres prac

- [ ] **A.** Raporty: zero oszczędności / baseline — zakładka **Koszty**
- [ ] **B.** Stawka €/km: domyślna z ustawień + override per pojazd
- [ ] **C.** Podsumowanie KPI: tylko w Raportach, bez `#N`, lepsze etykiety
- [ ] **D.** Operacje: przyciski tras przy tabeli Trasy; górny pasek = tylko akcje ogólne
- [ ] **E.** Generacje: niezależne od `is_busy` innych generacji; pełna flota w nowej
- [ ] **F.** Stan systemu: wczytanie / przywrócenie kopii zapasowej z daty

---

## A. Raporty — żadnych oszczędności, tylko koszty

### Problem

W raportach nadal pojawia się logika / tekst wokół „oszczędności” i baseline’u w stylu:

> Baseline: 1 zlecenie = 1 pojazd (2× km depot–drop × cost_per_km). Stawki Sandry (W-06) — placeholder.

To jest **niewiarygodne i nieprzydatne** dla dyspozytora. Nie ma być żadnej metryki „oszczędności vs baseline”.

### Oczekiwany efekt

1. **Usunąć całkowicie** z UI, Excelu i API raportów:
   - zakładkę / sekcję „Oszczędności”,
   - pola `savings_*`, baseline, tekst o W-06 / placeholderze,
   - porównania typu „oszczędność € / %” w podsumowaniu i eksporcie.
2. Zamiast tego: sekcja / zakładka **„Koszty”** — fakty z planu:
   - koszt per trasa / pojazd (km × stawka),
   - suma kosztów planu,
   - ewentualnie €/km efektywne per trasa (koszt / km),
   - **bez** fikcyjnego scenariusza „każde zlecenie osobno”.
3. Buforowanie (FR-022) może nadal używać wewnętrznej logiki „czy warto przytrzymać” — ale **nie** jako zakładka „oszczędności” w raporcie efektywności planu. Ewentualny % w propozycji bufora zostaje lokalnie przy Magazynie, nie w bloku „oszczędności planu”.

### Gotowe, gdy

- [ ] W `/reports`, kreatorze Excel i arkuszach brak słowa „oszczędność” / „baseline” w kontekście planu.
- [ ] Jest czytelna sekcja **Koszty**.
- [ ] Żaden toast / opis strony nie wspomina stawek Sandry jako „placeholder” w widoku użytkownika.

**Pliki:** `crossdock/services/reports.py`, `report_export_options.py`, `ui/report_builder.py`, `ui/pages.py` (Raporty), ewentualnie stare teksty w `docs/` / Word — nie pokazywać użytkownikowi.

---

## B. Koszt €/km — domyślny + ręcznie per samochód

### Problem

Dziś jest jedna globalna stawka `cost_per_km` w ustawieniach. Dyspozytor chce:

- **domyślną** stawkę jak teraz (Ustawienia → Parametry),
- oraz możliwość **ręcznej zmiany €/km dla konkretnego pojazdu**.

### Oczekiwany efekt

| Poziom | Zachowanie |
|--------|------------|
| Globalnie | `cost_per_km` w ustawieniach = domyślna stawka dla floty |
| Per pojazd | Pole opcjonalne `cost_per_km` (nullable) w modelu pojazdu |
| Liczenie kosztu trasy | `distance_km × (vehicle.cost_per_km ?? settings.cost_per_km)` |
| UI Flota | Przy edycji pojazdu: „€/km (puste = domyślne z ustawień)” |

### Gotowe, gdy

- [ ] Migracja Alembic: kolumna `cost_per_km` nullable na `vehicles`.
- [ ] Raport i plan używają stawki pojazdu, gdy ustawiona.
- [ ] Zmiana globalnej stawki nie nadpisuje ręcznych override’ów pojazdów.
- [ ] Test: dwa pojazdy, różne stawki → różne `cost_eur` przy tym samym dystansie.

---

## C. Podsumowanie KPI — tylko Raporty, czytelne etykiety

### Problem

1. Na górze Operacji **i** Raportów jest blok KPI generacji — w Operacjach jest **zbędny** (chipy / flota / trasy już dają obraz).
2. Tytuł zawiera numer generacji (`Generacja #6` / `· #6`) — **nie chcemy** tego w napisie podsumowania.
3. Etykiety są zbyt krótkie („Dystans”, „Koszt”, „Trasy”, „Pojazdy”).
4. Oszczędność w KPI — **wyrzucić** (jeśli jeszcze gdzieś jest).

### Oczekiwany efekt

**Gdzie:**

- Operacje (`/plans`): **usunąć** `GenerationKpiPanel` z góry strony.
- Raporty (`/reports`): **zostawić** podsumowanie KPI.

**Jak wygląda napis (bez `#N`):**

```
Szkic · 03.09 14:22          ← status + data, BEZ „Generacja #6”
────────────────────────────────────────────────────────
Zaplanowano: 42/50  ·  W magazynie: 5  ·  Wymaga uwagi: 3
Zaproponowane trasy: 8  ·  Przydzielone pojazdy: 8  ·  Śr. zapełnienie: 87%
Łączny dystans: 1 240 km  ·  Przybliżony koszt: 1 860 €
```

Mapowanie etykiet:

| Było | Ma być |
|------|--------|
| Trasy | Zaproponowane trasy |
| Pojazdy | Przydzielone pojazdy |
| Dystans | Łączny dystans |
| Koszt | Przybliżony koszt |
| Oszczędność… | *(usunąć)* |
| `Generacja #6 · …` | Status + data/godzina (opcjonalnie nazwa własna, jeśli nadana) — **bez numeru `#id`** |

Uwaga: historia generacji w tabeli audytu **może** nadal pokazywać ID (do rozróżnienia wierszy) — chodzi o **czytelny napis podsumowania**, nie o techniczny klucz w bazie.

### Gotowe, gdy

- [ ] Na Operacjach nie ma bloku KPI u góry.
- [ ] Na Raportach jest KPI z nowymi etykietami, bez `#id` w tytule.
- [ ] `format_plan_label` ma wariant „dla dyspozytora” bez numeru (lub osobna funkcja `format_plan_summary_title`).

**Pliki:** `ui/generation_kpi.py`, `ui/pages.py`, `text_pl.py`.

---

## D. Operacje — przyciski tras przy tabeli Trasy

### Problem

Górny pasek ma wszystko naraz: Generuj, Zatwierdź pełne, Zatwierdź trasę, Wyjechało, Zrealizowane, Odblokuj… Dyspozytor myli akcje **planowe** z akcjami **na zaznaczonej trasie**.

### Oczekiwany efekt

**Górny pasek (akcje ogólne):** np.

- Odśwież
- Generuj
- Zatwierdź pełne trasy
- Odblokuj zatwierdzone *(jeśli zostaje jako akcja masowa)*
- Pokaż na mapie
- Zaawansowane

**Przy tabeli Trasy (akcje na zaznaczeniu):**

- Zatwierdź trasę
- Wyjechało
- Zrealizowane
- Odblokuj trasę

Te same przyciski już są w powiększonym widoku tras — przenieść / zduplikować je **pod lub nad** kompaktową tabelą Trasy, a z głównego toolbara usunąć.

### Gotowe, gdy

- [ ] Górny pasek nie zawiera przycisków „Zatwierdź trasę / Wyjechało / Zrealizowane / Odblokuj trasę”.
- [ ] Te przyciski są widoczne przy tabeli Trasy (compact + enlarge).
- [ ] Hinty (`info_hint`) przeniesione razem z przyciskami.

**Plik:** `crossdock/ui/pages.py` (`plans` / Operacje).

---

## E. Generacje — poboczny feature, pełna flota w nowej

### Problem (model mentalny)

**Codzienna praca:** import zleceń → wielokrotne **Generuj** w **tej samej** aktywnej generacji. Solver dostosowuje się do dostępnych zleceń; zatwierdzone / w drodze / zrealizowane trasy są chronione.

**Nowa generacja** to **poboczny** feature: „zobacz całkowicie alternatywną ścieżkę planowania”. Nie jest to tryb codzienny.

**Bug / zła semantyka dziś:** jeśli w generacji A zatwierdzono trasę i pojazd ma `is_busy=True`, to **nowa generacja B** nie dostaje tego auta (`list_available()` filtruje `is_busy`). To psuje sens „alternatywnej ścieżki” — flota powinna być dostępna w całości do eksperymentu.

### Oczekiwany efekt

1. **Aktywna / codzienna generacja:**
   - Generuj respektuje chronione trasy (approved / in_transit / completed).
   - Pojazd zajęty **operacyjnie** (zatwierdzona / w drodze) nie wraca do solvera w tej generacji.

2. **Nowa generacja (alternatywna):**
   - Ma dostęp do **całej aktywnej floty** (nie dziedziczy `is_busy` z innej generacji).
   - Nie zmienia stanu operacyjnego floty „produkcyjnej”, dopóki użytkownik świadomie nie przełączy / nie zatwierdzi w kontekście tej generacji.
   - W UI: jasny opis w Zaawansowanych — „do porównań / eksperymentów, nie do codziennej pracy”.

3. **Technicznie (kierunek):**
   - `is_busy` nie może być globalnym lockiem między niezależnymi runami.
   - Zajętość pojazdu przy planowaniu = wynik **tras chronionych w bieżącym runie** (i ewentualnie realnego stanu floty tylko dla aktywnego planu operacyjnego), a nie „raz zajęty = zajęty wszędzie”.
   - `list_available()` przy `prepare_plan` / nowej generacji: nie wykluczać aut tylko dlatego, że są busy w innym runie.

### Do ustalenia (krótko)

- Czy zatwierdzenie trasy w **nieaktywnej** (historycznej) generacji w ogóle jest dozwolone? Rekomendacja: **nie** — albo tylko podgląd; zatwierdzanie tylko w aktywnym planie.
- Czy „Nowa pusta generacja” startuje od zera (same NEW orders), bez kopiowania chronionych tras?

### Gotowe, gdy

- [ ] Test: run A zatwierdza TRUCK-01 → nowy run B nadal widzi TRUCK-01 w puli solvera.
- [ ] Codzienne Generuj w aktywnym runie nadal chroni zatwierdzone trasy.
- [ ] Tekst w UI Zaawansowane wyjaśnia rolę generacji.

**Pliki:** `planning.py`, `repositories.py` (`list_available` / busy), `pages.py` (Zaawansowane).

---

## F. Stan systemu — wczytanie kopii z daty

### Problem

Dziś w **Stan systemu** można **utworzyć** kopię (`run_backup`), widać ostatnią kopię — **brak przywrócenia** bazy z wybranej daty / pliku.

### Oczekiwany efekt

W `/system`:

1. Lista dostępnych backupów (`data/backups/crossdock_YYYYMMDD_HHMM.db`) z datą i rozmiarem.
2. Akcja **„Wczytaj kopię”** / **„Przywróć”** dla wybranego pliku.
3. Potwierdzenie (dialog): „Nadpisze bieżącą bazę. Kontynuować?”.
4. Po przywróceniu: bezpieczne zamknięcie / restart połączeń SQLite, komunikat sukcesu, odświeżenie statusu.
5. Opcjonalnie: przed restore automatyczny backup „safety” bieżącego stanu.

### Bezpieczeństwo

- Tylko pliki z katalogu `backup_dir` (bez path traversal).
- Tylko użytkownik z uprawnieniami admin (jeśli role istnieją; dziś często jeden admin).
- Nie przywracać podczas trwającego Generuj (blokada / ostrzeżenie).

### Gotowe, gdy

- [ ] Lista backupów widoczna w Stan systemu.
- [ ] Restore z wybranej daty działa end-to-end (test na tmp DB).
- [ ] Po restore aplikacja pokazuje dane z tej kopii.

**Pliki:** `services/backup.py` (dodać `list_backups`, `restore_backup`), `ui/pages.py` (`system_page`).

---

## Kolejność wdrożenia

| Krok | Obszar | Dlaczego |
|------|--------|----------|
| 1 | A — wyciąć oszczędności / baseline | Natychmiastowa wiarygodność raportu |
| 2 | C — KPI tylko w Raportach + etykiety | Szybki UX, mały zakres |
| 3 | D — przyciski przy Trasy | Czytelność Operacji |
| 4 | B — €/km per pojazd | Migracja + użycie w koszcie |
| 5 | E — generacje / flota | Głębsza zmiana semantyki busy |
| 6 | F — restore backup | Ops / demo / odzyskiwanie |

---

## Czego oczekujemy w odpowiedzi

1. Krótki audyt: co z A–F już częściowo jest (np. `SavingsSummary` usunięte z `ReportBundle`, ale teksty / Excel / UI?).
2. Diff z testami (koszt per pojazd, flota w nowej generacji, restore backup).
3. Zaktualizowane polskie etykiety w jednym miejscu (`text_pl` / `generation_kpi`).

---

## Pliki kluczowe

| Plik | Temat |
|------|--------|
| `crossdock/services/reports.py` | Koszty zamiast oszczędności |
| `crossdock/services/report_export_options.py` | Sekcje Excel |
| `crossdock/ui/generation_kpi.py` | Etykiety KPI, bez `#id` |
| `crossdock/ui/pages.py` | Operacje, Raporty, System, Flota |
| `crossdock/text_pl.py` | `format_plan_label` / tytuł bez numeru |
| `crossdock/services/planning.py` | Flota przy nowej generacji |
| `crossdock/storage/tables.py` + Alembic | `vehicles.cost_per_km` |
| `crossdock/services/backup.py` | Lista + restore |
| `docs/jak_planowane_sa_trasy.md` | Spójność opisu (koszty, bez baseline) |
