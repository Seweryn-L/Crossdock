# Prompt: naprawa zakładki Magazyn — 3 problemy UX/danych

## Dla kogo i po co

**Odbiorca:** developer / agent AI pracujący nad Crossdock.

**Użytkownik końcowy:** dyspozytor korzystający z zakładki **Magazyn** (stan zapełnienia, kolejka wydań, trasy w drodze, buforowanie).

**Cel:** Naprawić trzy zgłoszone problemy, które psują zaufanie do ekranu magazynu i utrudniają codzienną pracę.

---

## Zakres prac

- [ ] **1.** Po „Zrealizowane” towar nadal liczy się w stanie magazynu
- [ ] **2.** W tabelach można „psuć” nagłówki kolumn (ukryć / przesunąć)
- [ ] **3.** Usunąć irytujący licznik / kaskadę powiadomień o błędach („clicker”)

---

## 1. Zrealizowane zlecenia nadal zajmują pojemność magazynu

### Problem (zgłoszenie użytkownika)

Po oznaczeniu trasy jako **Zrealizowane** zlecenia **wciąż** wliczają się do **Stan magazynu** (kg, %, liczba zleceń). Dyspozytor widzi przepełnienie lub towar, który już wyjechał.

### Oczekiwane zachowanie

Gdy trasa jest **zrealizowana** (`route_status = completed`, zlecenia `delivered`):

- towar **nie** wlicza się do `used_kg` / `fill_ratio` / `order_count` w bloku „Stan magazynu”,
- zlecenia **nie** pojawiają się w „Do kolejki” ani „Kolejka wydań”,
- trasa **znika** z sekcji „W drodze”,
- licznik magazynu odświeża się natychmiast po **Zrealizowane**.

### Prawdopodobna przyczyna w kodzie

`warehouse_snapshot()` (`crossdock/services/warehouse_stock.py`) liczy:

1. wszystkie zlecenia ze statusem **`new`**,
2. plus zlecenia z `view.holding_order_ids` (trasy „czekają na dopełnienie”).

**Brakuje filtra:** zlecenia ze statusem **`delivered`** (i ewentualnie inne zamknięte) są nadal dodawane do `holding`, jeśli pozostają w `holding_order_ids` planu — nawet po `complete_route()`.

Dodatkowo `list_queue()` (`warehouse_queue.py`) **nie pomija** zrealizowanych zleceń — wpis w kolejce może zostać, jeśli `_dequeue_orders` nie zadziałał lub użytkownik ominął krok **Wyjechało**.

`complete_route()` wymaga statusu trasy **`in_transit`** (najpierw **Wyjechało**, potem **Zrealizowane**). Jeśli dyspozytor klika **Zrealizowane** na trasie tylko zatwierdzonej, operacja się **nie udaje** — zlecenia zostają `approved` / `planned` i **nadal** mogą wpływać na magazyn przez inne ścieżki.

### Propozycja naprawy

**Backend (`warehouse_stock.py`):**

```text
Stan magazynu = tylko zlecenia faktycznie leżące w hubie:
  • status NEW (nie w drodze, nie dostarczone)
  • ORAZ opcjonalnie holding (czeka na dopełnienie), ale WYŁĄCZNIE gdy:
      - status ∈ {NEW, PLANNED}
      - trasa NIE jest completed / in_transit
      - zlecenie NIE jest DELIVERED
```

**Kolejka (`warehouse_queue.py`):**

- `list_queue()` — pomija zlecenia `delivered` (i ewentualnie czyści osierocone wpisy),
- po `complete_route()` — gwarantować dequeue (już jest `_dequeue_orders`; dodać test regresyjny).

**Magazyn UI (`pages.py` → `warehouse_page`):**

- sekcja „W drodze” — tylko trasy `in_transit` (już tak jest w `list_in_transit_routes`),
- dodać przycisk **Wyjechało** obok **Zrealizowane** (jak w Operacjach), żeby dyspozytor nie musiał przechodzić między zakładkami,
- po udanym **Zrealizowane** — `refresh_all()` i widoczny spadek kg w „Stan magazynu”.

### Do ustalenia

- Czy zlecenia **w drodze** (`in_transit`) mają **znikać** ze stanu magazynu już po **Wyjechało** (rekomendacja: **tak** — towar nie leży już w hubie)?
- Czy trasy **zatwierdzone**, ale jeszcze nie wyjechały, nadal liczą się do magazynu (rekomendacja: **nie**, jeśli towar jest już załadowany — albo osobna linia „załadowane na rampie”)?

### Gotowe, gdy

- [ ] Test: `complete_route` → `warehouse_snapshot.used_kg` maleje o wagę dostarczonych zleceń.
- [ ] Test: zlecenie `delivered` nigdy nie wraca do KPI magazynu.
- [ ] Test: kolejka nie pokazuje zrealizowanych zleceń.
- [ ] Ręcznie: **Wyjechało** → **Zrealizowane** na Magazynie → licznik kg spada, sekcja „W drodze” pusta.

---

## 2. Można „usunąć” / zepsuć nazwy kolumn w tabelach

### Problem (zgłoszenie użytkownika)

W gridach AG Grid na Magazynie (i prawdopodobnie innych zakładkach) użytkownik może **przeciągać nagłówki kolumn**, **ukrywać kolumny** z menu kontekstowego — tabela wygląda jak zepsuta, nagłówki znikają, dyspozytor nie wie co ogląda.

### Oczekiwane zachowanie

Tabele operacyjne są **sztywne**:

- nagłówki kolumn zawsze widoczne i nieedytowalne,
- brak przeciągania kolumn,
- brak menu „ukryj kolumnę” / panel kolumn,
- opcjonalnie: zmiana szerokości kolumny (resize) — do ustalenia; jeśli też myli, wyłączyć.

### Prawdopodobna przyczyna w kodzie

Grids na `/warehouse` (i część innych stron) mają `defaultColDef: { sortable, resizable }` **bez**:

- `suppressMovable: true`
- `suppressHeaderMenuButton: true` / `suppressMenu: true`
- `lockVisible: true`

Checkbox kolumna (`selection_column` w `widgets.py`) ma już `suppressMovable` — pozostałe kolumny nie.

### Propozycja naprawy

1. Dodać helper `grid_default_col_def()` w `crossdock/ui/widgets.py`:

```python
def grid_default_col_def(*, sortable: bool = True, resizable: bool = False) -> dict:
    return {
        "sortable": sortable,
        "resizable": resizable,
        "suppressMovable": True,
        "suppressHeaderMenuButton": True,
        "lockVisible": True,
    }
```

2. Użyć we **wszystkich** gridach Magazynu (i spójnie w całej aplikacji):
   - Do kolejki
   - Kolejka wydań
   - W drodze
   - Propozycja buforowania

3. Opcjonalnie: `suppressDragLeaveHidesColumns: true` na poziomie grid options.

### Gotowe, gdy

- [ ] Użytkownik nie może ukryć ani „zgubić” nagłówka kolumny w żadnej tabeli na Magazynie.
- [ ] Po odświeżeniu strony układ kolumn jest zawsze domyślny.
- [ ] Test UI (opcjonalnie): `columnDefs` w warehouse grids zawierają wymagane flagi.

---

## 3. Licznik błędów wygląda jak „clicker”

### Problem (zgłoszenie użytkownika)

Przy wielokrotnym nieudanym działaniu (np. **Zrealizowane** bez wcześniejszego **Wyjechało**) **wyskakują kolejne powiadomienia** z błędem — w rogu ekranu widać **rosnącą liczbę** (stack Quasar/NiceGUI `ui.notify`). Wygląda to jak licznik gier typu clicker i nie pomaga w pracy.

### Oczekiwane zachowanie

- **Jeden** czytelny komunikat o błędzie na akcję (nie 5 toastów przy zaznaczeniu 5 tras),
- brak kumulującego się badge’a z liczbą powiadomień,
- komunikat mówi **co zrobić** (np. „Najpierw kliknij Wyjechało”).

### Prawdopodobna przyczyna w kodzie

W `on_complete_in_transit()` (Magazyn) i podobnych handlerach:

- pętla po wielu trasach → wiele `ui.notify()` przy częściowych błędach,
- każde kliknięcie przy tym samym błędzie → kolejny toast,
- brak deduplikacji / `close` poprzedniego notify.

### Propozycja naprawy

1. **Jeden toast podsumowujący** zamiast wielu:

```text
Nie udało się zrealizować 3 tras:
  • TRUCK-01: najpierw kliknij „Wyjechało”
  • TRUCK-02: najpierw kliknij „Wyjechało”
```

2. Helper `notify_once(key, message, type)` — ten sam `key` w ciągu np. 3 s **nie** tworzy nowego toastu (aktualizuje istniejący lub ignoruje duplikat).

3. Dla znanych błędów — **polskie, operacyjne** komunikaty zamiast surowego `str(exc)`:
   - `match "w drodze"` → „Trasa nie wyjechała — najpierw **Wyjechało**.”

4. **Usunąć** ewentualny widoczny licznik błędów w UI (jeśli istnieje osobny element poza toastami) — zostawić tylko jednorazowy komunikat lub stały banner w sekcji, nie kumulujący się licznik.

### Gotowe, gdy

- [ ] 10× kliknięcie **Zrealizowane** przy tej samej trasie bez **Wyjechało** → max 1 widoczny komunikat (bez rosnącego badge’a).
- [ ] Zaznaczenie 5 tras z tym samym błędem → 1 podsumowanie, nie 5 toastów.
- [ ] Komunikat zawiera następny krok dla dyspozytora.

---

## Kolejność wdrożenia

| Krok | Zadanie | Priorytet |
|------|---------|-----------|
| 1 | Filtr `delivered` / `completed` w `warehouse_snapshot` + test | Krytyczny — błędne dane |
| 2 | Czyszczenie kolejki + przycisk **Wyjechało** na Magazynie | Wysoki — pełny flow |
| 3 | `grid_default_col_def()` na wszystkich gridach Magazynu | Średni — UX |
| 4 | `notify_once` + podsumowanie błędów batch | Średni — UX |

---

## Pliki do zmiany

| Plik | Zmiana |
|------|--------|
| `crossdock/services/warehouse_stock.py` | Wykluczyć `delivered` / trasy zamknięte z licznika kg |
| `crossdock/services/warehouse_queue.py` | Filtrować / czyścić kolejkę po realizacji |
| `crossdock/services/planning.py` | `complete_route` — upewnić się, że dequeue działa (test) |
| `crossdock/ui/pages.py` | `warehouse_page`: Wyjechało, refresh KPI, notify batch |
| `crossdock/ui/widgets.py` | `grid_default_col_def()`, ewentualnie `notify_once()` |
| `tests/services/test_sla_planning.py` | Test regresyjny: magazyn po `complete_route` |

---

## Czego oczekujemy w odpowiedzi

1. **Potwierdzenie root cause** dla pkt 1 (czy to `holding_order_ids` bez filtra statusu).
2. **PR / diff** z testami regresyjnymi.
3. **Krótki opis dla dyspozytora** (1 akapit): co się zmieniło w Magazynie po poprawce.
