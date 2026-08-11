# Plan tworzenia aplikacji — harmonogram tygodniowy

> Projekt: System optymalizacji cross-dockingu w logistyce transportowej
> Okres realizacji: **14.07.2026 → 15.09.2026** (9 tygodni)
> Powiązane dokumenty: `stack_technologiczny.md`, `karta_projektu_i_wdrozenia.md`, `notatka_srs.md`

---

## Założenia planu

- **Termin nieprzekraczalny:** 15.09.2026 — pokaz działającego produktu.
- **Minimum na demo (twarde):** planowanie transportów FTL na podstawie ręcznie wgranych plików Excel.
- **Obowiązkowo na demo:** mapa tras (efekt "wow") oraz ekran logowania z kontami użytkowników.
- **Dostępność:** praca w pełnym, stałym tempie przez cały okres (bez przerw urlopowych).
- **Sposób pracy:** kod pisany z pomocą AI — plan zakłada podwyższone tempo implementacji,
  ale tygodnie walidacji i testów pozostają nienaruszone (AI przyspiesza pisanie kodu,
  nie przyspieszają się debugowanie integracji, strojenie solvera ani testy na realnych danych).
  Testy automatyczne (pytest + hypothesis) są przy kodzie generowanym przez AI **ważniejsze, nie mniej ważne** —
  wyłapują sytuacje, gdy kod "wygląda dobrze, ale liczy źle".
- **Ścieżka krytyczna:** `import Excela → solver → prezentacja planu`. Wszystko inne jest dokładane
  wokół niej i w razie problemów może wypaść bez zabicia demo.

---

## Harmonogram

| Tydzień | Daty | Cel tygodnia | Efekt sprawdzalny na koniec tygodnia |
| :--- | :--- | :--- | :--- |
| **T1** | 14–20.07 | **Fundament + logowanie:** repo, uv, struktura modułów, SQLite + SQLAlchemy + Alembic, modele domenowe z testami (FR-019, FR-024), szkielet NiceGUI, ekran logowania, konta użytkowników z rolami (argon2), sesje | Aplikacja startuje, logowanie działa, testy domenowe przechodzą |
| **T2** | 21–27.07 | **Import + podstawowe ekrany:** parser pliku od firmy (mapowanie kolumn w konfiguracji), walidacja z raportem błędów per wiersz, lista zleceń (AG Grid: filtry, sortowanie), ekran ustawień floty (na tabeli od Martyny), słownik współrzędnych + macierz haversine | Wgranie prawdziwego pliku → zlecenia w tabeli z filtrami; flota edytowalna w UI |
| **T3** | 28.07–3.08 | **Solver, część 1 — przydział:** model CP-SAT (heterogeniczna flota, pojemności, nierozdzielność FR-019, maksymalizacja zapełnienia FR-011), `run.cpu_bound` z paskiem postępu, pierwsze testy własnościowe hypothesis | Realne zlecenia z importu przydzielone do pojazdów; testy niezmienników przechodzą |
| **T4** | 4–10.08 | **Solver, część 2 — trasy + plan w UI:** kolejność dropów, limit punktów rozładunku (FR-012), minimalizacja km (FR-014); ekran szczegółów planu (pojazd → zlecenia → kolejność → km/koszt), zatwierdzanie planu + audyt | Kompletny przepływ end-to-end: Excel → plan → przegląd → zatwierdzenie. **KAMIEŃ MILOWY: minimum na demo istnieje (5 tygodni przed terminem)** |
| **T5** | 11–17.08 | **Mapa (efekt wow, FR-016):** trasy na Leaflet — punkty rozładunku, linie tras per pojazd (kolory), popupy ze szczegółami zlecenia, podgląd trasy z poziomu planu | Kliknięcie planu → trasy wszystkich pojazdów widoczne na mapie |
| **T6** | 18–24.08 | **Raporty + operacje dyspozytorskie:** raport zapełnienia pojazdów i oszczędności z eksportem .xlsx (KPI wg Sandry, FR-017/018), edycja liczby palet po akceptacji (FR-021) z walidacją stanu i wpisem do audytu, kolejka magazynowa z ręczną rotacją (FR-020) | Raporty do pobrania; dyspozytor może zmienić palety i rotować kolejkę |
| **T7** | 25–31.08 | **Reguła buforowania (FR-022) + operacyjność:** heurystyka "wyślij vs buforuj" na stawkach Sandry (jej przykład liczbowy jako test), strona "Stan systemu", nocny backup bazy, baner statusu importu, dopracowanie UX (komunikaty błędów, puste stany, wskaźniki ładowania) | System sam proponuje, które zlecenia opłaca się przytrzymać; aplikacja "wykończona", nie surowa |
| **T8** | 1–7.09 | **Walidacja z zespołem:** scenariusze Patryka vs wyniki algorytmu (testy golden), strojenie solvera po feedbacku, realne stawki w konfiguracji, testy wydajności na pełnych danych, poprawki błędów | Zespół potwierdza sensowność planów logistycznie; znane błędy zamknięte |
| **T9** | 8–14.09 | **Wdrożenie + bufor:** instalacja na docelowym PC (uv sync, autostart, konta dla zespołu), dane demo, scenariusz pokazu, próba generalna. *Stretch (tylko jeśli wszystko gra):* OSRM w Dockerze → realne trasy drogowe na mapie zamiast linii prostych | System stoi na maszynie docelowej, demo przećwiczone |
| — | **15.09** | **POKAZ PRODUKTU** | |

---

## Zakres poza planem (świadomie, do realizacji po 15.09)

- **API TMS e2open + automatyczny harmonogram importu 5:30/11:30** — blokada zewnętrzna
  (oczekiwanie na dział IT klienta); architektura gotowa (port `OrderSource`).
- **Dane GPS floty** — źródło danych nieznane (Faza 2).
- **Realne trasy drogowe (OSRM)** — tylko jako stretch w T9; jeśli nie wejdzie przed pokazem,
  to naturalny pierwszy krok po demo. MVP liczy odległości w linii prostej (haversine),
  podmiana przez port `DistanceProvider` nie dotyka solvera.

---

## Mechanika bezpieczeństwa planu

1. **Kamień milowy "minimum działa" wypada już w T4** — od tego momentu każdy kolejny tydzień
   tylko dodaje wartość do działającego produktu. Czarny scenariusz (choroba, tydzień walki
   z OR-Tools) nie zagraża demo — co najwyżej zetnie FR-022 albo stretch z OSRM.
2. **Solver atakowany wcześnie (T3–T4)** — najryzykowniejszy element projektu jest rozpracowany
   6 tygodni przed terminem, nie 2.
3. **Kolejność cięcia zakresu w razie poślizgu (od pierwszego do wycięcia):**
   OSRM (stretch) → reguła buforowania FR-022 → kolejka magazynowa FR-020 →
   edycja palet FR-021 → raporty. Mapa i logowanie nie podlegają cięciu (decyzja: obowiązkowe na demo).
4. **T9 jest niemal pustym buforem** — realna praca to instalacja i próba generalna,
   reszta tygodnia absorbuje poślizgi.
5. **Testy jako zabezpieczenie kodu z AI** — niezmienniki solvera (hypothesis) i testy golden
   (scenariusze Patryka) pisane równolegle z funkcjami, nie po nich.

---

## Zależności od zespołu (wejścia do planu)

> **Status 20.07.2026:** T2 startuje bez finalnych danych od zespołu (placeholdery + fixture syntetyczny).
> Śledzenie braków, ownerów i checklisty po dostarczeniu: [`otwarte_wejscia_zespolu.md`](otwarte_wejscia_zespolu.md).
> Szczegółowy plan implementacji T2: [`plan_t2_implementacja.md`](plan_t2_implementacja.md).
> Szczegółowy plan implementacji T3: [`plan_t3_implementacja.md`](plan_t3_implementacja.md).
> Szczegółowy plan implementacji T4: [`plan_t4_implementacja.md`](plan_t4_implementacja.md).
> Szczegółowy plan implementacji T5: [`plan_t5_implementacja.md`](plan_t5_implementacja.md).
> Szczegółowy plan implementacji T6: [`plan_t6_implementacja.md`](plan_t6_implementacja.md).

| Wejście | Od kogo | Potrzebne najpóźniej | Blokuje | Status |
| :--- | :--- | :--- | :--- | :--- |
| Tabela floty (typy, wymiary, palety, ładowność) | Martyna | T2 | Ekran floty (T2), model solvera (T3) | **brak — seed placeholder** |
| Plik Excel marzec–kwiecień + instrukcja/lista braków raportu | Patryk | T2 | Parser importu (T2) | **sample e2open w fixtures podpięty; pełny okres + braki — od Patryka** |
| Słownik kolumn raportu od firmy | Sandra | T2 | Mapowanie kolumn importu (T2) | **mapowanie empiryczne z pliku; potwierdzenie Sandry nadal mile widziane** |
| Wstępne stawki kosztowe (km per typ pojazdu, doba magazynowania palety) | Sandra | T6 | Funkcja kosztu raportów (T6), reguła buforowania (T7) | czeka (T6) |
| Scenariusz wzorcowy "dobry plan" do porównania | Patryk | T8 | Walidacja golden (T8) | czeka (T8) |
| Odpowiedź firmy: skąd liczba palet w danych | firma / zespół | T3 | Pojemności w solverze (palety vs kg) | **brak — `pallet_count` opcjonalne** |
