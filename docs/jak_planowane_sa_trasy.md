# Jak planowane są trasy

Po **Generuj** system robi dwie osobne rzeczy. Najpierw **pakuje** zlecenia na auta. Dopiero potem **układa kolejność** przystanków. To nie jest jeden wielki rachunek „znajdź najtańsze trasy”.

---

## 1. Pakowanie (co jedzie z czym)

Biorą udział wyłącznie zlecenia ze statusem **nowe** (plus ewentualnie to, co już jest w szkicu planu i jeszcze nie jest zatwierdzone). Zlecenia wstrzymane w magazynie są pomijane.

Reguły twarde:

- całe zlecenie jedzie na jednym aucie (przesyłki pod jednym kodem nigdy się nie rozdzielają);
- waga na aucie nie przekracza ładowności;
- na jednej trasie jest najwyżej **N różnych punktów rozładunku** (domyślnie 3);
- zlecenie cięższe niż największe auto wypada z planu.

**Cel pakowania:** zmieścić jak najwięcej **kilogramów**, nie jak najmniej kilometrów i nie jak najniższy koszt.

Dlatego dwa pobliskie miasta mogą wylądować na dwóch autach, a dalekie na jednym — jeśli tak lepiej wypełni naczepy. Grupowania „w jednym kierunku” na tym etapie **nie ma**.

Punkt rozładunku to ten sam adres (współrzędne zaokrąglone do czterech miejsc, a gdy ich brak — miasto, kraj i nazwa). Dwa zlecenia pod ten sam dach to **jeden** przystanek.

---

## 2. Kolejność (jak jedzie auto)

Dla każdego załadowanego auta system układa kolejność punktów tak, by **suma odcinków w linii prostej** (magazyn → przystanki → magazyn) była jak najkrótsza.

To nie jest trasa po drogach. Mapa rysuje te same odcinki proste.

Jeśli po spakowaniu auto miałoby więcej przystanków niż limit, zostają te **najbliższe magazynowi** (przy remisie: cięższe). Reszta zleceń wraca do puli nieprzypisanych.

---

## 3. Co naprawdę steruje planem

| Ustawienie | Domyślnie | Co robi |
|---|---|---|
| Maks. punktów rozładunku | 3 | Twardy limit przy pakowaniu. `0` wyłącza limit (ryzyko „mleczarza”: dużo przystanków, pełna naczepa). |
| Limit czasu planowania | 45 s | Górny czas liczenia. Około 40% idzie na pakowanie, 60% na kolejność (minimum 5 s na etap). Przy wielu autach czas na kolejność dzieli się między nie. |
| Ziarno losowości | 42 | Powtarzalność **pakowania**. Przy tym samym wsadzie i tym samym ziarnie wychodzi ten sam rozkład. Kolejność przystanków tego ziarna nie używa. |
| Magazyn (szer./dł.) | Herentals | Punkt startu i powrotu, odległości, mapa. |
| Stawka €/km | 1,20 | **Nie** wpływa na to, kto z kim jedzie. Po ułożeniu trasy: koszt = kilometry w linii prostej × stawka. Liczba zastępcza, do czasu stawek z firmy. |

**Min. zapełnienie (0,90)** — tylko ostrzeżenie na planie i w raporcie. Planista **nie** musi dojść do 90%. Puste lub słabo wypełnione auto może zostać, jeśli nie ma czym go dopełnić.

**Domyślny termin dostawy** — przy imporcie, gdy w pliku nie ma daty: dziś + N dni. Na pakowanie nie wpływa.

---

## 4. Stawki i propozycja buforowania

To **osobna** logika na magazynie („Propozycja buforowania”), nie część **Generuj**.

Porównanie dla zlecenia, które nie weszło do pełnego auta:

- **Wysłać teraz jako drobnicę:** koszt = 2 × odległość magazyn–odbiorca × stawka €/km × **mnożnik drobnicy** (domyślnie 1,8).
- **Przetrzymać N dni i pojechać później całym autem:** koszt magazynu (palety × dni × €/paleta/dzień) + ten sam przejazd tam i z powrotem po stawce całopojazdowej.

Bufor pojawia się, gdy drugi wariant jest tańszy o co najmniej **próg oszczędności** (domyślnie 15%). System szuka **najkrótszego** N od 1 do **maks. dni buforowania** (domyślnie 3).

Gdy brak liczby palet, do kosztu magazynu przyjmuje 1 paletę.

Te kwoty są **szkicem**, nie cennikiem przewoźnika. Zmiana stawek zmienia propozycje i wyświetlany koszt planu; **nie przerabia** już wygenerowanych tras, dopóki nie naciśniesz **Generuj** ponownie.

---

## 5. Czego planista nie robi

- nie patrzy na palety ani objętość (tylko kilogramy i ładowność auta);
- nie zna okien czasowych u odbiorcy ani czasu pracy kierowcy;
- nie minimalizuje euro — euro liczy się na końcu ze stawki;
- nie grupuje po stronie świata;
- nie jeździ po drogach.

---

## 6. Jak tym sterować w praktyce

- **Za dużo „dziwnych” zestawów miast na jednym aucie** — obniż limit punktów (2) albo czekaj na grupowanie kierunkowe (jeszcze go nie ma).
- **Zostaje za dużo nieprzypisanych** — podnieś limit punktów (4–5) albo dołóż auta; pamiętaj, że wtedy trasy będą bardziej „mleczarskie”.
- **Za każdym razem inny plan** — zostaw ziarno; zmień je tylko gdy chcesz inną próbę przy tym samym wsadzie.
- **Za długie liczenie** — skróć limit czasu; przy dużym tygodniu wynik może być „dobry”, nie „dowiedziony jako najlepszy”.
- **Koszty na planie wyglądają nieprawdziwie** — popraw stawkę €/km; to tylko przelicznik kilometrów.
- **Propozycje magazynu nie mają sensu** — to te cztery liczby: stawka, mnożnik drobnicy, koszt palety/dzień, próg 15%. Dopóki nie ma prawdziwego cennika, to tylko kierunkowskaz.

Po zmianie parametrów w Ustawieniach trzeba **wygenerować plan od nowa**. Stary szkic sam się nie przeliczy.
