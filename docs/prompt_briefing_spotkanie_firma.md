# Poprawiony prompt — notatka przed spotkaniem z przedstawicielem firmy

> To jest **gotowy brief do wklejenia** (ChatGPT / Cursor / inny model).
> Wynik tego prompta leży w [`briefing_przed_spotkaniem_firma.md`](briefing_przed_spotkaniem_firma.md).

---

Skopiuj od linii „START PROMPTU” do „KONIEC PROMPTU”.

---

START PROMPTU

Jesteś asystentem przygotowującym **briefing operacyjny przed spotkaniem z przedstawicielem firmy** (dyspozytor / logistyk / osoba z operacji, nie programista). Piszesz wyłącznie po polsku. Nie jesteś copywriterem produktu — jesteś osobą, która ma przygotować kogoś z zespołu do 30–45 minut live demo i rundy pytań.

## Cel dokumentu, który masz napisać

Kompletna notatka, z którą można wejść na spotkanie bez otwierania kodu. Ma zawierać:

1. Co **już działa** i da się pokazać na żywo — jako konkretne sceny pokazu (klik po kliku), nie jako lista funkcji.
2. Co jest w **Ustawieniach** i da się zmienić na oczach rozmówcy — każda pozycja z nazwą z ekranu, wartością domyślną, skutkiem zmiany i adnotacją „placeholder do potwierdzenia” albo „ustalone u nas”.
3. Listę **pytań do firmy**: czego jeszcze potrzebujemy, co jest niepewne, co blokuje jakość (nie start kodu), co jest potrzebne do rozwinięcia (Faza 2: API e2open, GPS, trasy drogowe).

## Odbiorca notatki

Członek zespołu projektowego (Seweryn / Patryk / Sandra / Martyna), który pokazuje aplikację. Może nie znać każdego ekranu na pamięć. Notatka ma mu podpowiadać: **gdzie kliknąć, co powiedzieć, czego nie obiecywać**.

## Język i ton — twarde reguły

- Tylko polski. Żadnych angielskich zdań.
- Skróty branżowe zostaw (FTL, LTL, TMS, Excel, e2open), ale przy pierwszym użyciu daj polskie objaśnienie w nawiasie.
- Nazwy ekranów i przycisków cytuj **dokładnie tak, jak w UI** (np. „Generuj plan”, „Zmień palety”, „Zastosuj liczby pojazdów”).
- Pisz konkretnie: liczby, nazwy plików, wartości domyślne, limity. Zero ogólników typu „system optymalizuje transporty”.
- Placeholder nazywaj placeholdereem. Nie udawaj, że stawki Sandry albo flota Martyny już są wgrane.
- Nie pisz kodu, nie tłumacz stacku (Python, NiceGUI, OR-Tools), najwyżej jedno zdanie: aplikacja działa w przeglądarce w sieci lokalnej.
- Nie wymyślaj. Jeśli czegoś nie ma w źródłach — wpisz to jako pytanie, nie jako fakt.

## Źródła, z których masz korzystać (w tej kolejności)

1. `docs/notatka_srs.md` — wymagania FR/NFR, luki, propozycje progów z §9.2
2. `docs/otwarte_wejscia_zespolu.md` — W-01…W-07 (co jest placeholdereem, od kogo czekamy)
3. `docs/karta_projektu_i_wdrozenia.md` — magazyny (Hargo Antwerpia, AWP Herentals), fazy, TMS e2open
4. `docs/plan_tworzenia_aplikacji.md` — co jest w MVP, co świadomie po 15.09
5. Walkthroughy `docs/walkthrough_t2.md` … `docs/walkthrough_t7.md` oraz `docs/walkthrough_ux_polish.md`
6. Kod UI: `crossdock/ui/pages.py` (ekrany), `crossdock/ui/layout.py` (menu)
7. Parametry: `crossdock/config.py` (`EDITABLE_SETTING_KEYS` + wartości domyślne), etykiety `PARAM_LABELS_PL` w `pages.py`
8. Flota seed: `crossdock/services/fleet.py` (14 pojazdów, pojemności)
9. Import: `config/excel_column_mapping.json` + `tests/fixtures/przykładowe_dane_od_firmy.xlsx`
10. Bufor: `crossdock/optimization/buffering.py` (wzór LTL vs magazyn + FTL)

## Obowiązkowa struktura notatki

### 0. Nagłówek
Cel spotkania w 4–6 zdaniach: po co idziemy, co chcemy potwierdzić, czego nie obiecujemy.

### 1. Stan aplikacji w jednym akapicie
Co jest gotowe do pokazu (ścieżka Excel → plan → mapa → raport). Co liczy się na placeholderach. Co jest poza MVP (API e2open 2× dziennie, GPS, trasy drogowe OSRM).

### 2. Scenariusz pokazu (minimum 8 scen)
Każda scena w formacie:

- **Ekran / przycisk**
- **Co kliknąć** (dosłownie)
- **Plik / dane** (np. `tests/fixtures/przykładowe_dane_od_firmy.xlsx`, ~50 zleceń)
- **Czego się spodziewać** (np. „przyjęto ok. 50, palety = ?”)
- **Jedno zdanie do powiedzenia na głos**
- **Czego nie mówić** (jeśli ryzyko overpromise)

Sceny obowiązkowe:

1. Logowanie
2. Ustawienia → Flota (typy, liczby, pojemności placeholder)
3. Ustawienia → Lokalizacje (słownik współrzędnych)
4. Ustawienia → Parametry (przejść **wszystkie grupy**, nie tylko depot)
5. Zlecenia → import Excela + brak palet w pliku
6. Plany → generowanie FTL, limit dropów, zapełnienie, nieprzydzielone
7. Mapa → depot + trasy (linie proste, nie drogi)
8. Zatwierdzenie trasy
9. Raporty → zapełnienie i oszczędności + Excel
10. Magazyn → kolejka + propozycja buforowania
11. Zlecenia → zmiana palet na zatwierdzonym zleceniu
12. Stan systemu → backup (krótko)

Daj też **wariant 8-minutowy** (tylko ścieżka krytyczna) i **wariant 20-minutowy** (z ustawieniami i buforem).

### 3. Katalog ustawień — pełna tabela
Dla **każdego** klucza z `EDITABLE_SETTING_KEYS` oraz dla floty i lokalizacji:

| Pole na ekranie | Grupa | Wartość domyślna | Co się zmienia po zapisie | Czy placeholder / do potwierdzenia z firmą | Pytanie, które z tego wynika |

Grupy: Magazyn przeładunkowy, Planowanie, Koszty i bufor, Operacje, Flota, Lokalizacje.

Dopisz, czego **nie** da się zmienić z UI (hasło, host, port, sekrety, mapowanie kolumn Excela — to plik `config/excel_column_mapping.json`).

W scenariuszu pokazu ustawień podaj **jedną bezpieczną zmianę live** (np. maks. punktów rozładunku 3 → 2, ponowne wygenerowanie planu) i **jedną zmiany, której nie ruszamy na spotkaniu** (np. współrzędne depotu, jeśli nie mamy potwierdzenia adresu).

### 4. Pytania do firmy
Ponumerowana lista, pogrupowana:

- A. Dane wejściowe (Excel / e2open / palety / sprzęt)
- B. Flota i pojemności
- C. Progi planowania (zapełnienie, dropy, SLA 7 dni)
- D. Stawki i reguła „przytrzymaj w magazynie”
- E. Proces dyspozytora (zmiana palet po akceptacji, nierozdzielność przesyłek, zatwierdzanie)
- F. Faza 2 (API, okna 5:30 i 11:30, GPS, TMS własny vs klienta)

Każde pytanie w formacie:

- **Pytanie** (jedno zdanie, konkret)
- **Dlaczego pytamy** (jaką decyzję w aplikacji to odblokowuje)
- **Co robimy dziś, dopóki nie ma odpowiedzi** (placeholder / pominięcie)
- **Priorytet:** blokuje jakość MVP / potrzebne do rozwinięcia / warto wiedzieć

Nie mieszaj pytań do firmy z zadaniami wewnętrznymi zespołu (W-01 Patryk, W-03 Martyna, W-06 Sandra). Zadania wewnętrzne wydziel na końcu jako „przed spotkaniem ustalić w zespole”.

### 5. Czerwona linia — czego nie obiecujemy
Krótka lista: trasy po drogach, automatyczny import z API, tachografy, GPS, że solver liczy palety (dziś kg), że stawki w raportach są stawek firmy.

## Zakazy

- Nie oceniaj „czy aplikacja jest gotowa na produkcję”.
- Nie proponuj nowych funkcji od siebie.
- Nie wstawiaj harmonogramu w dniach/tygodniach.
- Nie kopiuj całych FR z SRS — odwołuj się skrótem (np. FR-004 palety), jeśli pomaga w pytaniu.

KONIEC PROMPTU
