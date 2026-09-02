# Jak planowane są trasy

Po **Generuj** system robi dwie osobne rzeczy. Najpierw **pakuje** zlecenia na auta. Dopiero potem **układa kolejność** przystanków. To nie jest jeden wielki rachunek „znajdź najtańsze trasy”.

Pakowanie zna **dzień planowania T** i **termin u odbiorcy**. Pełne auto może wyjechać wcześniej. Słabe czeka na dopełnienie (najlepiej ten sam odbiorca), dopóki nie nadejdzie ostatni legalny dzień wyjazdu.

---

## 1. Pakowanie (co jedzie z czym)

Biorą udział zlecenia ze statusem **nowe** oraz to, co już jest w szkicu planu i jeszcze nie jest zatwierdzone (w tym trasy **czekające na dopełnienie**). Zlecenia wstrzymane w magazynie są pomijane.

Reguły twarde:

- całe zlecenie jedzie na jednym aucie (przesyłki pod jednym kodem nigdy się nie rozdzielają);
- waga na aucie nie przekracza ładowności;
- na jednej trasie jest najwyżej **N różnych punktów rozładunku** (domyślnie 3);
- zlecenie cięższe niż największe auto wypada z planu.

**Cel pakowania:** zmieścić jak najwięcej **kilogramów**, z premią dla zleceń, które **muszą wyjechać dziś** (ostatni dzień wyjazdu, spóźnione, pozycja 1 w kolejce, overflow magazynu). Nie minimalizuje kilometrów ani kosztu.

Dlatego dwa pobliskie miasta mogą wylądować na dwóch autach, a dalekie na jednym — jeśli tak lepiej wypełni naczepy. Grupowania „w jednym kierunku” na tym etapie **nie ma**; ten sam odbiorca (`drop_key`) naturalnie zajmuje jeden przystanek i łatwiej dopełnia auto.

Punkt rozładunku to ten sam adres (współrzędne zaokrąglone do czterech miejsc, a gdy ich brak — miasto, kraj i nazwa). Dwa zlecenia pod ten sam dach to **jeden** przystanek.

---

## 2. Kolejność (jak jedzie auto)

Dla każdego załadowanego auta system układa kolejność punktów tak, by **suma odcinków w linii prostej** (magazyn → przystanki → magazyn) była jak najkrótsza.

To nie jest trasa po drogach. Mapa rysuje te same odcinki proste.

Jeśli po spakowaniu auto miałoby więcej przystanków niż limit, zostają te **najbliższe magazynowi** (przy remisie: cięższe). Reszta zleceń wraca do puli nieprzypisanych.

---

## 3. Terminy z importu (Pick / Drop Plan Date End)

Z raportu e2open importujemy **dwie daty końcowe**:

| Kolumna Excel | Pole w systemie | Znaczenie |
|---|---|---|
| `Pick Plan Date End` | wyjechać do (`must_leave_by`) | Ostatni dzień wyjazdu z magazynu |
| `Drop Plan Date End` | termin dostawy (`delivery_date`) | Termin dostawy u odbiorcy |

**Luz SLA** liczymy względem dnia planowania T:

- `luz = must_leave_by − T` (dni)

Gdy w imporcie brakuje `Pick Plan Date End`, system używa **fallbacku** z Ustawień: `must_leave_by = termin dostawy − N dni` (domyślnie N = 2). Gdy brak obu dat: termin dostawy = T + 7 dni, wyjazd z fallbacku.

| Luz | Co się dzieje |
|---|---|
| `> 0` | może czekać: pełne auto **jedzie**, słabe **zostaje** na dopełnienie |
| `= 0` | ostatni dzień wyjazdu: jedzie nawet przy 40% |
| `< 0` | spóźnione: i tak próbujemy wysłać dziś + czerwone ostrzeżenie |

Wcześniejszy wyjazd (np. 5 dni przed terminem) jest w porządku **tylko gdy** trasa osiąga **min. zapełnienie** (domyślnie 0,90). Słabe auto nie wyjeżdża „bo solver je spakował”.

Na jednym aucie wolno mieszać terminy i odbiorców (limit punktów zostaje). Sens cross-docku: dołożyć do tej samej naczepy kolejną przesyłkę **do tego samego odbiorcy**, albo — gdy zbliża się `must_leave_by` i nie ma dopełnienia — połączyć z innym kierunkiem / wysłać niepełne.

---

## 4. Jedzie / czeka / zostaje poza FTL

Po spakowaniu trasa dostaje decyzję, **zanim** zatwierdzisz plan:

| Decyzja | Kiedy | Status zlecenia |
|---|---|---|
| **Wyślij** | zapełnienie ≥ próg **albo** na trasie jest zlecenie z luzem ≤ 0 **albo** magazyn pęka | po **Zatwierdź pełne trasy** → zatwierdzone |
| **Czeka na dopełnienie** | spakowana, ale poniżej progu i wszystkie zlecenia mają luz > 0 | zostaje `planned` w szkicu; **nie** wchodzi w „Zatwierdź pełne trasy” |
| **Zostaje poza FTL** | `UNASSIGNED` — brak miejsca w flocie | `new`, wraca do puli |

**Zatwierdź trasę** (pojedynczo) nadal może wysłać słabe auto ręcznie.

Przy **Następny dzień** + **Generuj** niezatwierdzone 40% wraca do solvera razem z nowym importem. Jeśli doszło zlecenie na ten sam `drop_key`, wpadnie na tę samą naczepę (limit punktów + waga). Jeśli nie — albo dopełni się innym towarem, albo w dniu `must_leave_by` wyjedzie niepełne.

---

## 5. Co naprawdę steruje planem

| Ustawienie | Domyślnie | Co robi |
|---|---|---|
| Dzień planowania | kalendarz | Sztuczne dziś (T) do SLA, importu bez daty i bufora. |
| Fallback wyjazdu [dni] | 2 | Gdy brak Pick Plan Date End w imporcie: ostatni wyjazd = termin − N. |
| Pojemność magazynu | 50 000 kg | Monitoring na Magazynie; overflow wypycha najpilniejsze. |
| Maks. punktów rozładunku | 3 | Twardy limit przy pakowaniu. `0` wyłącza limit (ryzyko „mleczarza”). |
| Limit czasu planowania | 45 s | Górny czas liczenia. Około 40% idzie na pakowanie, 60% na kolejność. |
| Ziarno losowości | 42 | Powtarzalność **pakowania**. Kolejność przystanków tego ziarna nie używa. |
| Magazyn (szer./dł.) | Herentals | Punkt startu i powrotu, odległości, mapa. |
| Stawka €/km | 1,20 | **Nie** wpływa na to, kto z kim jedzie. Po ułożeniu trasy: koszt = km × stawka. |
| Min. zapełnienie | 0,90 | Próg **Wyślij** vs **Czeka na dopełnienie**, gdy jest luz SLA. |
| Domyślny termin dostawy | 7 dni | Przy imporcie bez daty: T + N, nie systemowe dziś. |

Po zmianie parametrów w Ustawieniach trzeba **wygenerować plan od nowa**. Stary szkic sam się nie przeliczy.

---

## 6. Magazyn: pojemność, kolejka, priorytet

Ekran **Magazyn** pokazuje stan dnia:

- **kg w hubie** = zlecenia `new` + trasy czekające na dopełnienie, względem **pojemności** (placeholder do potwierdzenia z firmą);
- odliczanie do najbliższego `must_leave_by`;
- **overflow** (stan > pojemność) → solver i widok planu wymuszają wysyłkę tras o najmniejszym luzie, z ostrzeżeniem.

**Kolejka wydań:** pozycja 1 (nie wstrzymana) jest traktowana jak must-ship — pakowana pierwsza. Kolumny: termin, wyjechać do, luz, waga, odbiorca. Dyspozytor może wymusić wyjazd (góra kolejki / zatwierdź trasę) albo przytrzymać (wstrzymaj).

---

## 7. Stawki i propozycja buforowania

To **osobna** logika na magazynie („Propozycja buforowania”), nie część **Generuj**.

Porównanie dla zlecenia, które nie weszło do pełnego auta:

- **Wysłać teraz jako drobnicę:** `K_teraz = 2 × d × s × m`
- **Przetrzymać N dni i pojechać później całym autem:** `K_bufor(N) = (p × N × c) + (2 × d × s)`

gdzie `d` = odległość magazyn–odbiorca, `s` = stawka €/km, `m` = mnożnik drobnicy (domyślnie 1,8),
`p` = palety (brak w danych → 1), `c` = €/paleta/dzień (domyślnie 2,00).

Bufor pojawia się, gdy `K_bufor(N) ≤ K_teraz × (1 − τ)` — domyślnie τ = 15%. System szuka **najkrótszego** N od 1 do **maks. dni buforowania** (domyślnie 3), **ściętego do luzu względem `must_leave_by`** (nie względem terminu u odbiorcy). Przy luzie ≤ 0 zawsze **wyślij teraz**.

**Przykład:** d = 100 km, s = 1,20, m = 1,8, p = 2 → `K_teraz` = 432 €, `K_FTL` = 240 €, przy N = 1 magazyn 4 € → `K_bufor` = 244 € (oszczędność ≈ 43,5%) → **przytrzymaj 1 dzień**.

Te kwoty są **szkicem**, nie cennikiem przewoźnika.

---

## 8. Oszczędności w Raportach (KPI)

Baseline (koszt odniesienia): scenariusz **1 zlecenie = 1 pojazd** — każde zlecenie na trasie jedzie samotnie w obie strony.

- `K_odniesienia = Σ (2 × dᵢ × s)` po zleceniach na trasach (z współrzędnymi)
- `K_plan = Σ (km_trasy × s)` — suma kosztów tras planu
- `Oszczędność € = K_odniesienia − K_plan`
- `Oszczędność % = (Oszczędność € / K_odniesienia) × 100`

Stawka `s` = Parametry → Stawka €/km (`cost_per_km`). Zapełnienie w raporcie = waga / ładowność.

**Przykład:** dwa zlecenia, d = 100 km, s = 1,20 → baseline 480 €; jedno auto (200 km) → 240 €; oszczędność 240 € (50%).

---

## 9. Czego planista nie robi

- nie patrzy na palety ani objętość (tylko kilogramy i ładowność auta);
- nie zna okien czasowych u odbiorcy, czasu jazdy po drogach ani tachografu;
- nie minimalizuje euro — euro liczy się na końcu ze stawki;
- nie grupuje po stronie świata (poza limitem punktów i tym samym `drop_key`);
- nie odpalają się same wszystkie dni tygodnia — każdy dzień T to osobne **Generuj**.

---

## 10. Jak tym sterować w praktyce

- **Pokaz z danymi e2open (kwiecień 2026)** — ustaw T na kilka dni przed najwcześniejszym terminem, **Generuj**: 90%+ jedzie, ~40% czeka; **Następny dzień** i kolejne **Generuj** dokłada do tego samego miasta albo wymusza wyjazd przed terminem−2.
- **Za dużo „dziwnych” zestawów miast na jednym aucie** — obniż limit punktów (2).
- **Zostaje za dużo nieprzypisanych** — podnieś limit punktów (4–5) albo dołóż auta.
- **Słabe auta wyjeżdżają za wcześnie** — sprawdź, czy T nie jest już ostatnim dniem wyjazdu albo czy magazyn nie jest ponad pojemność.
- **Za każdym razem inny plan** — zostaw ziarno.
- **Za długie liczenie** — skróć limit czasu.
- **Propozycje magazynu nie mają sensu** — stawka, mnożnik drobnicy, koszt palety/dzień, próg 15% i luz SLA.

---

## 11. Cykl trasy — co oznaczają statusy

**Dzień planowania T** to sztuczne „dziś” (Ustawienia albo pole na planie). **Następny dzień** przesuwa T o jeden dzień.

| Status trasy | Etykieta w UI | Co to znaczy operacyjnie |
|---|---|---|
| `proposed` | propozycja | Solver zaproponował — do decyzji |
| `approved` | gotowa do jazdy | Plan zaakceptowany, auto zajęte, jeszcze na rampie |
| `in_transit` | w drodze | Kierowca wyjechał (przycisk **Wyjechało**) |
| `completed` | zrealizowana | Auto wróciło (przycisk **Zrealizowane**), pojazd wolny |

Kolejność przycisków: **Zatwierdź trasę** → **Wyjechało** → **Zrealizowane**.

Zrealizowane trasy **nie znikają z bazy** przy kolejnym **Generuj**, ale domyślnie są **ukryte** na Planie i Mapie (filtr „Pokaż zrealizowane” / „Bieżące”). Panel **Trasy w drodze** pokazuje tylko status `in_transit`.

Na liście **Zleceń** domyślnie widać aktywne rekordy (bez zrealizowanych); kolumny **Termin dostawy** i **Wyjechać do** pochodzą wprost z importu TMS.
