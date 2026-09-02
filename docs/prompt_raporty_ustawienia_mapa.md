# Prompt: raporty, ustawienia, mapa — ulepszenia UX dla dyspozytora

## Dla kogo i po co

**Odbiorca:** zespół produktowy / developer / agent AI pracujący nad Crossdock.

**Użytkownik końcowy:** dyspozytor (ocena planu po **Generuj**) oraz osoba zarządzająca operacjami (porównanie generacji).

**Cel:** Po wygenerowaniu planu użytkownik **od razu** widzi jakość wyniku, problemy i wpływ ustawień — bez przeskakiwania między Operacjami, Raportami i Mapą.

> To nie jest budowa od zera. Aplikacja ma już: chipy w Operacjach, zakładkę „Wymaga uwagi”, Raporty z historią generacji, Ustawienia (Flota / Lokalizacje / Parametry), Mapę z legendą i popupem trasy.

---

## Zakres prac (5 obszarów)

- [ ] **A.** Podsumowanie KPI po generacji
- [ ] **B.** Porównanie dwóch generacji
- [ ] **C.** Rozbicie kategorii „Wymaga uwagi”
- [ ] **D.** Ustawienia: grupy + opisy + przypomnienie o **Generuj**
- [ ] **E.** Mapa: filtr problemów + alerty w popupie trasy

---

## A. Podsumowanie KPI po generacji

### Obecny stan

Po **Generuj** dyspozytor widzi chipy (jedzie / zostaje / wymaga uwagi) i tabele tras, ale **nie ma jednego bloku z liczbami**. Żeby ocenić wynik, musi wejść w Raporty lub liczyć ręcznie.

### Oczekiwany efekt

Na górze **Operacji** (zaraz po generacji) i w **Raportach** (dla wybranej generacji) — jeden panel KPI:

| Metryka | Znaczenie dla dyspozytora |
|---------|--------------------------|
| Zlecenia poddane planowaniu | Ile zleceń solver wziął pod uwagę |
| Zlecenia zaplanowane | Przypisane do tras („jedzie”) |
| Zlecenia w magazynie | Czekają na dopełnienie lub poza FTL |
| Liczba tras | Ile tras w tej generacji |
| Wykorzystane pojazdy | Ile aut faktycznie jedzie |
| Średnie zapełnienie | Czy flota jest dobrze wykorzystana |
| Całkowity dystans | Suma km |
| Szacowany koszt | Suma € (stawka z ustawień) |
| Szacowana oszczędność | Oszczędność vs scenariusz „każde zlecenie osobno” |

**Przykład:**

```
Generacja #12 · szkic
────────────────────────────────────────────────────
Zaplanowano 42/50  ·  W magazynie: 5  ·  Wymaga uwagi: 3
Trasy: 8  ·  Pojazdy: 8  ·  Śr. zapełnienie: 87%
Dystans: 1 240 km  ·  Koszt: 1 860 €  ·  Oszczędność: 320 € (15%)
```

### Do ustalenia

- Czy KPI jest zawsze widoczne, czy tylko po **Generuj**?
- Czy „w magazynie” i „wymaga uwagi” liczymy osobno (rekomendacja: **tak**)?
- Te same liczby w Operacjach i Raportach muszą się **zgadzać**.

### Gotowe, gdy

- [ ] Dyspozytor ocenia generację bez zmiany zakładki.
- [ ] Liczby = suma z tabel tras + zakładki „Wymaga uwagi”.
- [ ] Pusta generacja → komunikat, nie puste pola.

**Źródło danych w kodzie:** `PlanSummary`, `ReportBundle` (`crossdock/services/plan_view.py`, `reports.py`).

---

## B. Porównanie generacji

### Obecny stan

W **Raportach → Historia generacji** jest lista (ID, km, koszt, data) i podgląd na mapie. **Brak porównania** dwóch uruchomień.

### Oczekiwany efekt

Po zaznaczeniu **dwóch** wierszy w historii — panel delt:

```
Generacja #12 vs #11
────────────────────
  −2 pojazdy
  −87 km
  +4% średniego zapełnienia
  +120 € oszczędności
  +1 zlecenie czeka w magazynie
```

Kolory: zielony = poprawa, czerwony = pogorszenie (mniej km = dobrze; więcej zleceń w magazynie = źle).

### Do ustalenia

- Porównujemy tylko szkice, czy też zatwierdzone plany?
- MVP metryk: pojazdy, km, zapełnienie, koszt, oszczędność, zlecenia w magazynie — wystarczy?
- Eksport porównania (Excel) — teraz czy później?

### Gotowe, gdy

- [ ] 2 zaznaczone generacje → widoczne delty.
- [ ] 0–1 zaznaczenie → panel ukryty + komunikat „Zaznacz dwie generacje”.
- [ ] „Podgląd na mapie” działa jak dotąd.

---

## C. „Wymaga uwagi” — nie tylko liczba

### Obecny stan

System ma kategorię **Wymaga uwagi** (lista w Operacjach), ale w podsumowaniu widać tylko:

> Wymaga uwagi: 5

Dyspozytor nie wie **dlaczego**, dopóki nie otworzy listy.

### Oczekiwany efekt

Pod liczbą — rozbicie przyczyn:

```
5 zleceń wymaga uwagi
  • 3 — brak współrzędnych odbiorcy
  • 1 — przekroczona ładowność pojazdów
  • 1 — przekroczony termin wyjazdu
```

Klik w wiersz przyczyny → filtruje listę / mapę do tych zleceń (opcjonalnie w MVP, ale warto zaplanować).

### Do ustalenia

- Pełna lista kategorii problemów (minimum: współrzędne, waga, termin, limit punktów rozładunku).
- Gdzie pokazywać rozbicie: Operacje + Raporty + Mapa (rekomendacja: **wszędzie tam, gdzie jest licznik**).

### Uwaga techniczna

Dziś `REASON_ATTENTION` to jeden ogólny tekst. Potrzebny enum przyczyn + polskie etykiety w UI (`plan_view.py`).

### Gotowe, gdy

- [ ] Po **Generuj** widać liczbę **i** rozbicie.
- [ ] Etykiety zrozumiałe dla dyspozytora (bez kodów technicznych).
- [ ] Spójność z filtrem mapy (pkt E).

---

## D. Ustawienia — podział i opisy

### Obecny stan

Zakładka **Parametry** miesza ustawienia codzienne z technicznymi. Brak opisu „co robi ten parametr”. Po zapisie użytkownik może nie wiedzieć, że trzeba ponownie kliknąć **Generuj**.

### Oczekiwany efekt

**Trzy grupy widoczności:**

| Grupa | Parametry (przykłady) | Kto zmienia |
|-------|----------------------|-------------|
| **Planowanie transportu** | flota, ładowność, max punktów rozładunku, min. zapełnienie, wyprzedzenie wyjazdu | dyspozytor, codziennie |
| **Koszty** | €/km, magazynowanie, mnożnik LTL, próg buforowania | dyspozytor / kierownik |
| **Zaawansowane** (zwinięte) | backup, solver, upload, współrzędne magazynu | admin |

**Przy każdym parametrze** — krótki opis, np.:

> **Minimalne zapełnienie: 90%**  
> Określa, przy jakim poziomie zapełnienia trasa może wyjechać automatycznie.

**Po zapisie parametru wpływającego na solver:**

> Zmiana wymaga ponownego wygenerowania planu — kliknij **Generuj** w Operacjach.

Opcjonalnie: baner lub link „Przejdź do Operacji” do czasu następnego **Generuj**.

### Do ustalenia

- Które parametry **nie** wymagają regeneracji (np. sam €/km w raporcie)?
- Zaawansowane: accordion czy osobna zakładka?
- Dostęp do Zaawansowanych: wszyscy czy tylko admin?

### Gotowe, gdy

- [ ] Parametry codzienne oddzielone od technicznych.
- [ ] Każdy parametr biznesowy ma 1–2 zdania opisu po polsku.
- [ ] Po zapisie krytycznego parametru — widoczne przypomnienie o **Generuj**.

---

## E. Mapa — problemy na pierwszy rzut oka

### Obecny stan

Mapa ma legendę pojazdów, filtr statusu trasy i popup po kliknięciu (status, dropy, km, koszt). **Brak szybkiego filtra problemów** i **brak alertów** w popupie.

### Oczekiwany efekt — dwie zmiany

#### E1. Filtr „Pokaż tylko problemy”

W legendzie lub na pasku nad mapą — jeden przełącznik. Po włączeniu mapa pokazuje tylko:

- zlecenia/trasy z kategorii **Wymaga uwagi**,
- trasy poniżej progu zapełnienia,
- zlecenia spóźnione / w ostatnim dniu wyjazdu.

Przy 0 problemach: „Brak problemów — wszystko OK”.

#### E2. Alerty w popupie trasy

Na górze popupu (po kliknięciu trasy), jeśli jest problem:

```
⚠ Uwaga: 1 zlecenie wymaga uwagi
   Brak współrzędnych odbiorcy — uzupełnij w Ustawieniach → Lokalizacje.
```

```
⚠ Zapełnienie 62% — poniżej progu 90%. Trasa czeka na dopełnienie.
```

### Do ustalenia

- Ta sama definicja „problemu” co w pkt C (rekomendacja: **tak**).
- Alert tylko po kliknięciu, czy też w tooltip (hover)?
- Link „Uzupełnij współrzędne” / „Przejdź do zlecenia” — teraz czy później?

### Gotowe, gdy

- [ ] Jeden klik na mapie = tylko problematyczne elementy.
- [ ] Popup od razu mówi, co jest nie tak — bez szukania w innych zakładkach.
- [ ] Filtr problemów nie psuje pozostałych ustawień legendy.

**Źródło w kodzie:** `map_view.py` (`detail_html`, `tooltip_html`), `pages.py` (legenda mapy).

---

## Spójność między ekranami

| Pojęcie | Operacje | Raporty | Mapa | Ustawienia |
|---------|----------|---------|------|------------|
| Zlecenia zaplanowane | chip „jedzie” | KPI | trasa na mapie | — |
| W magazynie | chip „zostaje” | KPI / delta | — | — |
| Wymaga uwagi | chip + lista + rozbicie | KPI + rozbicie | filtr + popup | — |
| Min. zapełnienie | tabela tras | raport per pojazd | alert w popupie | parametr + opis |

**Zasada:** te same liczby i te same polskie nazwy wszędzie.

---

## Kolejność wdrożenia (rekomendacja)

| Krok | Obszar | Uzasadnienie |
|------|--------|--------------|
| 1 | A — KPI po generacji | Największy zysk, dane już w `PlanSummary` / `ReportBundle` |
| 2 | C — rozbicie „Wymaga uwagi” | Fundament pod mapę i raporty |
| 3 | E2 — alerty w popupie | Korzysta z pkt C |
| 4 | E1 — filtr problemów na mapie | Korzysta z pkt C |
| 5 | B — porównanie generacji | Metryki per run częściowo już zapisane |
| 6 | D — restrukturyzacja ustawień | Głównie UX, bez zmian solvera |

---

## Czego oczekujemy w odpowiedzi

1. **Audyt** — co z powyższego jest już częściowo zrobione.
2. **Mockup tekstowy** — układ KPI i panelu porównania.
3. **Lista zmian w kodzie** — np. enum `AttentionReason`, nowe pola w `AssignmentRun`.
4. **MVP na jeden sprint** — które checkboxy z zakresu prac da się domknąć.
5. **Pytania do klienta** — definicja „problemu”, lista parametrów Zaawansowanych.

---

## Pliki w repozytorium

| Plik | Co tam szukać |
|------|----------------|
| `crossdock/services/plan_view.py` | `PlanSummary`, „Wymaga uwagi”, `REASON_*` |
| `crossdock/services/reports.py` | `ReportBundle`, oszczędności, tabela per pojazd |
| `crossdock/ui/pages.py` | Operacje, Raporty, Mapa, Ustawienia |
| `crossdock/services/map_view.py` | popup i tooltip trasy |
| `crossdock/services/app_settings.py` | zapis parametrów |
| `docs/jak_planowane_sa_trasy.md` | logika zapełnienia, SLA, bufor |
