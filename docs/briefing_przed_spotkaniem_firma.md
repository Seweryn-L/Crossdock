# Notatka przed spotkaniem z przedstawicielem firmy

**Aplikacja:** Crossdock — planowanie transportów całopojazdowych (FTL) z magazynu przeładunkowego.
**Na kiedy:** briefing do live demo 30–45 min + rundy pytań.
**Dla kogo w zespole:** osoba pokazująca aplikację (nie musi znać kodu).
**Plik demo:** `tests/fixtures/przykładowe_dane_od_firmy.xlsx` (raport e2open, nagłówek w 3. wierszu, ok. 50 zleceń, wagi w kg, **brak kolumny palet**).

Powiązane: [SRS](notatka_srs.md) · [otwarte wejścia W-01…W-07](otwarte_wejscia_zespolu.md) · [karta projektu](karta_projektu_i_wdrozenia.md) · [poprawiony prompt](prompt_briefing_spotkanie_firma.md)

---

## 0. Cel spotkania

Idziemy pokazać **działający obieg dyspozytora**: wgrać prawdziwy raport Excel z TMS e2open, dostać plan FTL (pełne auta z cross-docku), zobaczyć trasy na mapie, ściągnąć raport zapełnienia i oszczędności. Chcemy, żeby rozmówca zobaczył też **Ustawienia** — to tam siedzą progi, które dziś są naszymi propozycjami ze specyfikacji, a nie stawkami ani regułami firmy.

Spotkanie ma **potwierdzić albo skorygować** te progi i braki w danych (głównie: skąd liczba palet, jaka jest prawdziwa flota, jakie stawki €/km i magazynowania). Nie obiecujemy integracji API, GPS ani tras po drogach — tego nie ma w tej wersji i jest świadomie odłożone.

Jedno zdanie na otwarcie: *„To wersja robocza na pliku Excel. Algorytm już grupuje zlecenia w auta i układa kolejność rozładunków. Część liczb w ustawieniach jest tymczasowa — właśnie po to tu jesteśmy, żeby je ustalić.”*

---

## 1. Stan aplikacji — co mówić w 40 sekund

**Działa i da się pokazać:** logowanie → import Excela → lista zleceń → wygenerowanie planu FTL (limit punktów rozładunku, zapełnienie wagowe) → mapa z magazynem i trasami → zatwierdzenie trasy → raport Excel → kolejka magazynowa i propozycja „przytrzymaj towar” → ręczna zmiana palet na zatwierdzonym zleceniu → kopia zapasowa bazy.

**Liczy się na liczbach tymczasowych:** pojemności 14 pojazdów (seed, nie tabela Martyny), stawka 1,20 €/km, koszt magazynu 2 €/paleta/dzień, mnożnik drobnicy 1,8, próg oszczędności bufora 15%. Solver **nie używa palet** — w Excelu ich nie ma, więc planuje po **kilogramach**.

**Nie ma i nie pokazujemy jako gotowe:** automatyczne pobieranie z API e2open dwa razy dziennie (5:30 i 11:30), monitoring GPS, trasy po prawdziwych drogach (na mapie są **linie proste**), czas pracy kierowców / tachograf (poza zakresem projektu).

Aplikacja stoi lokalnie w przeglądarce (sieć LAN), nie w chmurze firmy.

---

## 2. Scenariusz pokazu

Przed spotkaniem: baza wyczyszczona albo świadomie z jednym czystym importem; w Ustawieniach → Lokalizacje wczytany słownik współrzędnych; flota seed 14 pojazdów aktywna.

### Wariant 8 minut (ścieżka krytyczna)

Logowanie → Zlecenia (import) → Plany (Generuj plan) → Mapa → Raporty. Ustawienia tylko jeśli zapytają.

### Wariant 20 minut (rekomendowany)

Ustawienia (Flota + Parametry) → import → plan → mapa → zatwierdzenie jednej trasy → raport → magazyn (bufor) → zmiana palet.

### Wariant 35–40 minut

Pełne 12 scen poniżej, z jedną zmianą parametru na żywo (maks. punktów rozładunku 3 → 2 i ponowne generowanie).

---

### Scena 1 — Logowanie

- **Ekran:** `/login`
- **Co kliknąć:** nazwa `admin`, hasło z lokalnego `.env`, „Zaloguj się”.
- **Czego się spodziewać:** pulpit z liczbami (zlecenia, ostatni plan, kolejka, ostatni import) i skrótami.
- **Powiedzieć:** *„To narzędzie dla dyspozytora. Na razie konta lokalne, nie logowanie z e2open.”*
- **Nie mówić:** że będzie SSO / konta z TMS.

### Scena 2 — Ustawienia → Flota

- **Ekran:** Ustawienia (ikona koła zębatego) → zakładka **Flota**
- **Co pokazać:** trzy typy: `bus` (10 palet / 3 500 kg), `truck` (20 palet / 12 000 kg), `curtain` / plandeka (33 palety / 24 000 kg). Liczby aktywnych: 2 busy + 4 ciężarówki + 8 plandek = **14**. Tabela z kodami `BUS-01` … `CURTAIN-08`. Przycisk **Zastosuj liczby pojazdów** oraz edycja pojedynczego pojazdu (kod, typ, palety, kg, aktywny).
- **Powiedzieć:** *„Tu ustawiacie, ile aut jakiego typu jedzie do planu. Pojemności są robocze — czekamy na waszą tabelę floty. Pojazd z zatwierdzoną trasą nie da się wyłączyć.”*
- **Nie mówić:** że te 10/20/33 palety to wasze realne naczepy.

### Scena 3 — Ustawienia → Lokalizacje

- **Ekran:** zakładka **Lokalizacje**
- **Co kliknąć (jeśli pusto):** **Wczytaj słownik lokalizacji**, potem ewentualnie **Uzupełnij współrzędne w zleceniach**.
- **Czego się spodziewać:** wpisy nazwa / miasto / kraj / lat / lon. Bez współrzędnych punkt **nie wjedzie na mapę** i trasa może być bez sekwencji.
- **Powiedzieć:** *„Excel z e2open ma adresy tekstem, nie GPS. My dokładamy współrzędne słownikiem. Jeśli odbiorca nie ma wpisu — nie narysujemy dropu.”*

### Scena 4 — Ustawienia → Parametry (obowiązkowo, nie na odczepnego)

- **Ekran:** zakładka **Parametry** → **Zapisz parametry**
- **Co przejść głosowo, grupa po grupie:**

  **Magazyn przeładunkowy** — szerokość 51,176 / długość 4,836 (roboczy punkt ok. Herentals, ~30 km od Antwerpii). Start wszystkich tras.

  **Planowanie** — min. zapełnienie 0,90 (90%); maks. punktów rozładunku **3**; limit czasu planowania 45 s; ziarno 42 (ten sam wynik przy tych samych danych); domyślny termin dostawy **7 dni**, gdy w pliku nie ma daty.

  **Koszty i bufor** — 1,20 €/km; 2 € za paletę za dzień; mnożnik drobnicy 1,8; próg oszczędności 0,15 (15%); maks. 3 dni przytrzymania. To **placeholdery**, nie stawki Sandry / firmy.

  **Operacje** — limit Excela 20 MB; 14 kopii zapasowych; nocna kopia o 2:30.

- **Zmiana live (bezpieczna):** `Maks. punktów rozładunku` 3 → 2, zapisz, potem w Planach wygeneruj plan jeszcze raz. Pokazać, że trasy mają najwyżej 2 dropy.
- **Czego nie zmieniać na spotkaniu:** współrzędnych magazynu (dopóki nie potwierdzą adresu), stawek (dopóki nie podadzą swoich).
- **Powiedzieć:** *„Te liczby nie są w kodzie na sztywno. Dyspozytor zmienia je tu. Chcemy usłyszeć, które są OK, a które do wymiany.”*

Czego **nie ma** na tym ekranie: hasło, adres serwera, sekrety, mapowanie kolumn Excela (to plik konfiguracyjny, nie UI).

### Scena 5 — Zlecenia → import

- **Ekran:** **Zlecenia** → **Importuj z Excela**
- **Plik:** `tests/fixtures/przykładowe_dane_od_firmy.xlsx` (nie drugi plik TMS w funtach — to inny format).
- **Czego się spodziewać:** baner „przyjęto ~50, pominięto 0, błędy 0” (przy pustej bazie). Tabela: kod dostawy, odbiorca, miasto, termin, status „nowe”, liczba przesyłek, **Palety = ?**, waga w kg. Zlecenie z tym samym kodem dostawy przy kolejnym imporcie jest **pomijane**, nie nadpisywane.
- **Powiedzieć:** *„Bierzemy raport e2open jak z portalu. Nagłówek jest w trzecim wierszu — tak jest w waszym eksporcie. Palet w tym pliku nie ma, dlatego solver dziś pakuje po wadze.”*
- **Nie mówić:** że drugi plik (funty / stopy sześcienne) też jest domyślnym importem.

### Scena 6 — Plany → generowanie FTL

- **Ekran:** **Plany**
- **Co kliknąć:** **Generuj plan** (poczekać — pasek, do ~45 s). Nie klikać w kółko.
- **Czego się spodziewać:** trasy z pojazdem, km, kosztem (€ = km × 1,20), kolejnością dropów; zapełnienie %; lista **zleceń na trasie** i **zleceń, które nie weszły** (zostają w hubie). Nagłówek strony mówi wprost o limicie dropów i stawce z ustawień.
- **Powiedzieć:** *„Cel: pełne auta, mało rozładunków, ten sam kierunek. Dwie przesyłki pod jednym zleceniem jadą zawsze razem — tego nie da się rozdzielić.”*
- **Nie mówić:** że odległości to kilometry drogowe (to linia prosta). Nie mówić, że 100% zleceń zawsze wsiądzie — przy 14 autach część może zostać.

### Scena 7 — Mapa

- **Ekran:** z Planów **Pokaż na mapie**, albo menu **Mapa**
- **Czego się spodziewać:** punkt magazynu, kolorowe polilinie per pojazd, strzałki kierunku, klik w marker → kod / miasto. Legenda.
- **Powiedzieć:** *„To podgląd kierunków, nie nawigacja. Drogi i korki dojdą później, jeśli będziecie chcieli.”*

### Scena 8 — Zatwierdzenie trasy

- **Ekran:** **Plany** → zatwierdź **pojedynczą** trasę (nie cały run naraz, jeśli UI pokazuje trasy osobno).
- **Czego się spodziewać:** status zleceń → zatwierdzone; pojazd **zajęty** i wypada z kolejnych generacji; kolejne „Generuj plan” nie rusza zatwierdzonego.
- **Powiedzieć:** *„Dyspozytor akceptuje auto po aucie. Resztę można przeliczyć jeszcze raz.”*

### Scena 9 — Raporty

- **Ekran:** **Raporty** → **Pobierz Excel**
- **Czego się spodziewać:** zapełnienie % per pojazd, km, koszt; oszczędność względem scenariusza **1 zlecenie = 1 pojazd**. Arkusze „Zapełnienie” / „Oszczędności”.
- **Powiedzieć:** *„Oszczędność jest liczona naszą stawką 1,20 €/km. Jak podacie realne stawki, te same wykresy przeliczą się same.”*
- **Nie mówić:** że to już KPI zaakceptowane przez kontroling firmy.

### Scena 10 — Magazyn: kolejka i bufor

- **Ekran:** **Magazyn**
- **Kolejka:** z listy „nowe” → **Dodaj do kolejki** → góra / dół / usuń. To ręczny priorytet wydań (całe zlecenie).
- **Bufor:** **Odśwież propozycję** → widać „przytrzymaj” vs „wyślij teraz”, liczba dni, % oszczędności. Zaznaczyć „przytrzymaj” → akceptacja wrzuca do kolejki ze statusem wstrzymane.
- **Powiedzieć:** *„Reguła: jeśli magazyn + późniejszy pełny samochód jest tańszy o co najmniej 15% od wysyłki drobnicą teraz — system proponuje poczekać, maksymalnie 3 dni. Próg i stawki są w Ustawieniach.”*
- **Uwaga:** przy paletach = ? heurystyka podstawia **1 paletę** do kosztu magazynu — kolejny powód, by dopytać o palety.

### Scena 11 — Zmiana palet po zatwierdzeniu

- **Ekran:** **Zlecenia** → zaznaczyć **jedno** zlecenie ze statusem zatwierdzone → **Zmień palety**
- **Czego się spodziewać:** zapis nowej liczby; jeśli nie mieści się w aucie — ostrzeżenie „wymaga przeplanowania”, **bez** automatycznego przeliczenia planu.
- **Powiedzieć:** *„To jest sytuacja z życia: po akceptacji klient zmienia ilość. Dziś zapisujemy i ostrzegamy. Chcemy ustalić, do której godziny wolno zmieniać i co robić, gdy auto już nie wchodzi.”*

### Scena 12 — Stan systemu (krótko)

- **Ekran:** **Stan systemu** → **Utwórz backup teraz**
- **Powiedzieć:** *„Baza i logi lokalnie, kopia nocna. Nie wysyłamy nic na zewnątrz.”*

---

## 3. Katalog ustawień

Zmiany z zakładki **Parametry** zapisują się od razu (plik lokalny nakładany na konfigurację). Hasła i adres serwera — poza tym ekranem.

### 3.1 Parametry (edytowalne z UI)

| Pole na ekranie | Grupa | Domyślnie | Co się zmienia po zapisie | Placeholder / do potwierdzenia | Pytanie |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Szerokość geograficzna magazynu | Magazyn | 51,176 | Start/koniec tras, km, mapa, koszt, bufor | Roboczy punkt ~Herentals, nie geokod z adresu | Czy magazyn to na pewno Grensstraat 3, 2200 Herentals? Dokładny GPS? |
| Długość geograficzna magazynu | Magazyn | 4,836 | j.w. | j.w. | j.w. |
| Min. zapełnienie (0–1) | Planowanie | 0,90 | Solver dąży do ≥90% ładowności **wagowej**; poniżej — ostrzeżenie w planie | Propozycja z SRS (90%) | 90% po kg, po paletach, czy po objętości? Twarde minimum czy cel? |
| Maks. punktów rozładunku | Planowanie | 3 | Twardy limit dropów na trasie | Propozycja z SRS (max 3) | Czy 3 to limit operacyjny, czy bywa 4–5? Wyjątki? |
| Limit czasu planowania [s] | Planowanie | 45 | Ile sekund wolno liczyć plan | Techniczne, nie biznes | Raczej nie pytać firmy |
| Ziarno losowości | Planowanie | 42 | Ten sam wynik przy tych samych danych | Techniczne | Raczej nie pytać firmy |
| Domyślny termin dostawy [dni] | Planowanie | 7 | Gdy w Excelu brak daty: dziś + 7 dni kalendarzowych | Ze spotkania („zazwyczaj 7 dni”) | Czy 7 dni od importu, od akceptacji, czy od załadunku u Hargo? Weekendy wliczone? |
| Stawka €/km | Koszty i bufor | 1,20 | Koszt trasy, raport oszczędności, porównanie LTL/FTL | **W-06**, nie stawka firmy | Jaka stawka za km? Czy różna dla bus / ciężarówka / plandeka? |
| Koszt magazynu €/paleta/dzień | Koszty i bufor | 2,00 | Heurystyka „przytrzymaj” | **W-06** | Jaki realny koszt doby palety w Herentals? |
| Mnożnik drobnicy (LTL) | Koszty i bufor | 1,8 | Koszt „wyślij teraz” = 1,8 × koszt FTL tam i z powrotem | **W-06**, bardzo uproszczone | Jak wyceniacie LTL vs FTL? Macie taryfę, czy % narzutu? |
| Próg oszczędności bufora (0–1) | Koszty i bufor | 0,15 | Bufor tylko gdy oszczędność ≥ 15% | Propozycja SRS 15% | 15% jest OK, czy inny próg? Kto go może zmienić? |
| Maks. dni buforowania | Koszty i bufor | 3 | Górny limit przytrzymania | Propozycja, nie SLA firmy | Ile dni towar **może** stać w AWP? Czy 3 to za mało / za dużo? |
| Limit uploadu Excel [MB] | Operacje | 20 | Odrzut pliku powyżej limitu | Techniczne | Jaka typowa wielkość raportu e2open? |
| Ile kopii zapasowych trzymać | Operacje | 14 | Rotacja backupów | Techniczne | — |
| Godzina / minuta nocnej kopii | Operacje | 2:30 | Harmonogram backupu | Techniczne | — |

### 3.2 Flota (zakładka Flota)

| Co widać | Domyślnie (seed) | Co zmienia | Do potwierdzenia |
| :--- | :--- | :--- | :--- |
| Typ `bus` | 10 palet, 3 500 kg, 2 szt. | Ile busów wchodzi do solvera | Czy w ogóle macie busy w tej pracy? Realna ładowność? |
| Typ `truck` | 20 palet, 12 000 kg, 4 szt. | j.w. | Tabela floty: wymiary, palety, kg |
| Typ `curtain` | 33 palety, 24 000 kg, 8 szt. | j.w. | Mapowanie sprzętu z Excela: „Flatbed” i „EU: 09 CURTAIN / BOX TRAILER” → u nas plandeka |
| Pojedynczy pojazd | kod, typ, palety, kg, aktywny | Edycja / dopisanie | Czy planować tylko aktywną flotę dnia, czy „papierową” maksymalną? |
| Zajęty | po zatwierdzeniu trasy | Nie da się dezaktywować | Czy zatwierdzenie = auto wyjechało, czy tylko plan na papierze? |

### 3.3 Lokalizacje (zakładka Lokalizacje)

Słownik nazwa + miasto + kraj + kod pocztowy + GPS. Bez wpisu nie ma punktu na mapie i bywa brak kolejności dropów. **Pytanie:** czy współrzędne macie w TMS, czy mamy je utrzymywać ręcznie?

### 3.4 Poza UI — nie obiecywać, że „się klika w ustawieniach”

| Temat | Gdzie naprawdę | Status |
| :--- | :--- | :--- |
| Mapowanie kolumn raportu | `config/excel_column_mapping.json` | Empiryczne z pliku; **W-02** czeka na słownik Sandry / firmy |
| Aliasy sprzętu | ten sam plik (`Flatbed` → plandeka) | Do potwierdzenia |
| Hasło admina, sekret sesji, host/port | plik `.env` | Nie na spotkaniu z firmą |
| API e2open | niezaimplementowane (port gotowy, brak danych IT) | Faza 2 |

---

## 4. Pytania do firmy

Priorytet: **blokuje jakość MVP** / **potrzebne do rozwinięcia** / **warto wiedzieć**.

### A. Dane wejściowe (Excel / e2open)

1. **W którym polu raportu e2open jest (albo będzie) liczba palet?**  
   *Dlaczego:* wymaganie FR-004; dziś palety = puste, solver liczy kg, bufor udaje 1 paletę.  
   *Dziś:* nie wymyślamy palet.  
   *Priorytet:* blokuje jakość MVP (**W-04**).

2. **Czy ten eksport (`Order Ref`, `TMS ID`, `Product Weight` w kg, `Drop Plan Date Start`, nagłówek w 3. wierszu) to wasz standard, czy wyjątek?**  
   *Dlaczego:* mapowanie kolumn jest z jednego sample.  
   *Dziś:* jeden parser pod ten układ.  
   *Priorytet:* blokuje jakość MVP (**W-02**).

3. **Czy waga w raporcie to waga ładunku netto, brutto, z paletą?** Jednostka zawsze kg?  
   *Dlaczego:* zapełnienie 90% stoi na tej liczbie.  
   *Dziś:* bierzemy `Product Weight` jako kg.  
   *Priorytet:* blokuje jakość MVP.

4. **Drugi plik (funty, stopy sześcienne, adres tylko nazwą odbiorcy) — używacie go operacyjnie?**  
   *Dlaczego:* nie chcemy budować drugiego parsera „na wszelki wypadek”.  
   *Dziś:* nie jest domyślnym importem.  
   *Priorytet:* warto wiedzieć.

5. **Słownik sprzętu: „Flatbed” vs „EU: 09 CURTAIN / BOX TRAILER” — to te same naczepy, czy inne ograniczenia (np. flatbed nie weźmie plandeki)?**  
   *Dlaczego:* oba mapujemy na `curtain`.  
   *Dziś:* alias w konfiguracji.  
   *Priorytet:* blokuje jakość MVP.

6. **Jedno zlecenie (`Order Ref`) = ile numerów przesyłek (`TMS ID`) w praktyce? Zawsze 1–2, czy bywa więcej?**  
   *Dlaczego:* nierozdzielność jest twarda: wszystkie shipmenty zlecenia jadą razem.  
   *Dziś:* zakaz rozdzielania niezależnie od liczby.  
   *Priorytet:* warto wiedzieć.

7. **Czy origin w raporcie to zawsze Hargo (Scheldelaan 373, Antwerpia), a my planujemy tylko nogę z Herentals do odbiorców?**  
   *Dlaczego:* depot w ustawieniach jest jeden.  
   *Dziś:* wszystkie trasy startują z jednego GPS magazynu przeładunkowego.  
   *Priorytet:* blokuje jakość MVP.

### B. Flota i pojemności

8. **Prosimy o tabelę floty: typ, liczba sztuk, palety, kg, ewentualnie wymiary / objętość.**  
   *Dlaczego:* 14 aut i pojemności 10/20/33 palet to seed demonstracyjny (**W-03**).  
   *Dziś:* da się to wpisać w Ustawieniach → Flota, ale liczby są zgadnięte.  
   *Priorytet:* blokuje jakość MVP.

9. **Czym ograniczać załadunek: palety, kg, objętość, czy wszystkie trzy?**  
   *Dlaczego:* dziś tylko kg (+ palety w karcie pojazdu, ale bez danych w zleceniu).  
   *Priorytet:* blokuje jakość MVP.

10. **Czy plan ma brać tylko auta dostępne danego dnia, czy pełną flotę „na papierze”?**  
    *Dziś:* wszystkie aktywne, minus zajęte po zatwierdzeniu.  
    *Priorytet:* warto wiedzieć.

### C. Progi planowania

11. **Czy minimum 90% zapełnienia jest twardym warunkiem, czy celem?** Po jakiej osi (kg / palety / m³)?  
    *Dziś:* 0,90 w ustawieniach, liczone wagowo.  
    *Priorytet:* blokuje jakość MVP.

12. **Czy maksymalnie 3 punkty rozładunku na auto to wasza reguła?** Wyjątki (np. jeden kierunek, małe dropy)?  
    *Dziś:* twardy limit 3, zmieniany w Parametrach.  
    *Priorytet:* blokuje jakość MVP.

13. **7 dni kalendarzowych — od jakiego momentu i czy to SLA twarde?**  
    *Dziś:* brak daty w pliku → import + 7 dni.  
    *Priorytet:* warto wiedzieć.

14. **Plany mają być gotowe 4–5 dni przed wysyłką — przed wysyłką z Hargo czy z Herentals? Kto je zatwierdza?**  
    *Dziś:* generowanie ręczne, zatwierdzanie w UI.  
    *Priorytet:* potrzebne do rozwinięcia (harmonogram).

### D. Stawki i bufor magazynowy

15. **Jakie stawki przyjąć do raportu: €/km per typ auta, ryczałt, taryfa strefowa?**  
    *Dziś:* jedna stawka 1,20 €/km (**W-06**).  
    *Priorytet:* blokuje jakość raportów.

16. **Koszt doby palety w AWP Herentals — kwota?**  
    *Dziś:* 2 €.  
    *Priorytet:* blokuje jakość bufora.

17. **Jak porównujecie „wyślij drobnicę teraz” vs „poczekaj na FTL”?** Macie mnożnik, taryfę LTL, czy decyzję uznaniową?  
    *Dziś:* LTL = 1,8 × FTL (tam i z powrotem), próg 15%, max 3 dni.  
    *Priorytet:* blokuje jakość bufora.

18. **Ile dni towar może fizycznie stać w cross-docku?** Są towary, których nie wolno buforować (ADR, data ważności, klient VIP)?  
    *Dziś:* jeden limit 3 dni na wszystkie zlecenia.  
    *Priorytet:* blokuje jakość MVP.

### E. Proces dyspozytora

19. **Po akceptacji zlecenia klient zmienia palety — do którego momentu wolno to wgrać?** (np. 12 h przed załadunkiem)  
    *Dziś:* edycja tylko statusu zatwierdzone; przy przepełnieniu ostrzeżenie, bez auto-replanu.  
    *Priorytet:* blokuje jakość MVP.

20. **Gdy po zmianie palet auto już nie wchodzi: rozdzielić na drugie auto (zakazane przy wspólnych shipmentach), zdjąć z trasy, czy przeliczyć cały plan?**  
    *Dziś:* tylko warning.  
    *Priorytet:* blokuje jakość MVP.

21. **Zatwierdzenie trasy w naszej aplikacji = co w waszym procesie?** (plan wewnętrzny / wysyłka do e2open / dyspozycja kierowcy)  
    *Dziś:* blokada pojazdu i zleceń w naszej bazie, nic nie wraca do TMS.  
    *Priorytet:* potrzebne do rozwinięcia.

22. **Kto ma prawo zmieniać Parametry (stawki, limit dropów) — tylko admin, czy każdy dyspozytor?**  
    *Dziś:* każdy zalogowany z dostępem do Ustawień.  
    *Priorytet:* warto wiedzieć.

### F. Faza 2 — rozwinięcie

23. **API e2open: czy dział IT może podać dokumentację (endpointy, auth, środowisko testowe)? Kiedy?**  
    *Dziś:* ręczny Excel; architektura ma port na podmianę źródła.  
    *Priorytet:* potrzebne do rozwinięcia.

24. **Okna 5:30–6:00 i 11:30–12:00 — to nadal aktualne godziny zrzutu? Czas belgijski?**  
    *Dziś:* niezaimplementowane.  
    *Priorytet:* potrzebne do rozwinięcia.

25. **Czy macie własny TMS poza e2open klienta, do którego mamy oddawać gotowy plan?**  
    *Dziś:* nic nie eksportujemy do TMS (tylko Excel raportu).  
    *Priorytet:* potrzebne do rozwinięcia.

26. **GPS floty — jakie źródło (telematyka, e2open, nic)?**  
    *Dziś:* brak.  
    *Priorytet:* potrzebne do rozwinięcia.

27. **Czy linie proste na mapie wystarczą operacyjnie, czy do decyzji potrzebujecie km drogowych (autostrada vs granica)?**  
    *Dziś:* haversine; OSRM odłożone.  
    *Priorytet:* warto wiedzieć / rozwinięcie.

28. **Język UI jest polski, raport e2open angielski — czy dyspozytorzy w BE/NL potrzebują angielskiego / niderlandzkiego interfejsu?**  
    *Priorytet:* warto wiedzieć.

---

## 5. Przed spotkaniem ustalić w zespole (nie pytać firmy o to, co mamy w domu)

| ID | Kto | Co | Po co na spotkaniu |
| :--- | :--- | :--- | :--- |
| W-01 | Patryk | Pełny Excel marzec–kwiecień + lista braków raportu | Żeby nie obiecywać, że sample = cały sezon |
| W-02 | Sandra | Oficjalny słownik kolumn | Jedno pytanie do firmy zamiast zgadywania nazw |
| W-03 | Martyna | Tabela floty — choćby robocza | Pokazać w Ustawieniach realne liczby, nie seed |
| W-06 | Sandra | Stawki €/km, doba palety, LTL | Żeby raport nie był „1,20 z kapelusza” |
| W-07 | Patryk | Jeden „dobry plan” wzorcowy | Późniejsza walidacja, nie na to spotkanie |

---

## 6. Czerwona linia — czego nie obiecujemy

- Tras po drogach, ETA, korków, winiet.
- Automatycznego importu z API ani zrzutu 5:30 / 11:30.
- GPS, tachografów, czasu pracy kierowców (to **poza zakresem**).
- Że solver **już** pakuje po paletach — **nie pakuje**, bo ich nie ma w pliku.
- Że 1,20 €/km, 2 €/paleta/dzień i 15% to liczby firmy.
- Że plan wraca do e2open jednym przyciskiem.
- Że drugi format Excela (funty) jest obsługiwany tak samo.
- 100% przydzielonych zleceń przy każdej flocie.

Jeśli zapytają „kiedy API”: *„Moduł źródła danych jest pod wymianę. Blokada jest po stronie dostępu do API, nie po stronie klikania w Excel. Na dziś liczy się, żebyście potwierdzili palety, flotę i stawki — bez tego API i tak policzy to samo, tylko automatycznie.”*
