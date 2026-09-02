# Prompt: doprecyzowanie cyklu życia trasy i widoczności zleceń (Magazyn / Plan / Zlecenia)

**Cel:** Wyjaśnić dyspozytorowi (i ewentualnie poprawić w aplikacji) co oznaczają statusy tras i zleceń, skąd biorą się daty terminów oraz gdzie w procesie brakuje informacji o **czasie wyjazdu** i **czasie powrotu**.

**Kontekst biznesowy:** Dyspozytor pracuje w trybie ciągłej operacji (import → plan → magazyn → wysyłka). Musi szybko znaleźć właściwe rekordy i wiedzieć, **kiedy auto faktycznie rusza**, a nie tylko kiedy „zatwierdził plan”.

---

## 1. Zrealizowane trasy nadal mieszają się z aktywnymi

**Problem:** Trasy/zlecenia oznaczone jako **zrealizowane** wciąż pojawiają się w widokach z **propozycjami** i **zatwierdzonymi** trasami. Dyspozytor musi dłużej szukać rekordów i nie wie, co jest jeszcze do zrobienia, a co już zamknięte.

**Pytania do odpowiedzi:**

- Czy zrealizowane trasy powinny znikać z planu / magazynu / mapy domyślnie?
- Czy w **Zleceniach** filtr „Aktywne (bez zrealizowanych)” wystarcza, czy też plan i magazyn potrzebują osobnego filtra „tylko otwarte”?
- Czy zrealizowane mają być widoczne tylko w raportach / historii?

**Oczekiwany efekt:** Domyślny widok pokazuje wyłącznie to, co wymaga decyzji lub jest w toku. Zrealizowane = archiwum, nie szum w bieżącej pracy.

---

## 2. Termin wysyłki — z danych importu, nie ze sztywnego „2 dni wcześniej”

**Problem:** Dyspozytor oczekuje, że **data wysyłki / ostatni dzień wyjazdu** pochodzi wprost z importu (Excel / TMS). Obecnie system liczy `must_leave_by = termin u odbiorcy − N dni` (domyślnie **2 dni**), co może nie odpowiadać rzeczywistości operacyjnej.

**Pytania do odpowiedzi:**

- Czy w imporcie jest osobna kolumna typu „must ship by” / „data wyjazdu z magazynu”, czy tylko **termin dostawy u odbiorcy**?
- Jeśli jest tylko termin dostawy: czy **2 dni** to reguła firmy (konfigurowalna), czy błąd w założeniu?
- Co pokazywać w UI: termin dostawy, ostatni dzień wyjazdu, czy oba — z jasnym opisem skąd każdy pochodzi?

**Oczekiwany efekt:** Termin decyzyjny dla magazynu jest zgodny z danymi od klienta (lub z uzgodnioną regułą biznesową), a nie ukrytym domyślnym parametrem.

---

## 3. Ile czekać na dopełnienie auta przed wysyłką?

**Problem:** Na etapie **zatwierdzania** nie wiadomo, **jak długo** auto może czekać na dopełnienie, zanim musi wyjechać (pełne lub niepełne). Dyspozytor nie ma progu „maksymalnie X godzin/dni czekamy na ten sam odbiorca / to samo auto”.

**Pytania do odpowiedzi:**

- Czy limit wynika wyłącznie z `must_leave_by` (luz dni), czy jest też limit **operacyjny** (np. max 4 h na rampie)?
- Co system powinien pokazać przy trasie „czeka na dopełnienie”: ile dni/godzin zostało do ostatniego legalnego wyjazdu?
- Kiedy auto **musi** wyjechać mimo niskiego zapełnienia (ostatni dzień wyjazdu, overflow magazynu)?

**Oczekiwany efekt:** Przy każdej trasie w buforze widać: zapełnienie, ostatni dzień wyjazdu, ile jeszcze można czekać — bez zgadywania.

---

## 4. Co znaczy „Zatwierdź”? Brak momentu startu trasy

**Problem:** Etykieta **„zatwierdzone”** sugeruje, że kierowca **od razu jedzie**. W praktyce zatwierdzenie oznacza raczej: „plan zaakceptowany, auto zajęte, towar ma wyjechać”, ale **nie ma w systemie zdarzenia „wyjechało o HH:MM”**. Dyspozytor może oznaczyć tylko **powrót** („Zrealizowane”). Brakuje **czasu rozpoczęcia realizacji** trasy.

**Pytania do odpowiedzi:**

- Czy zmienić nazewnictwo: np. **„zatwierdzone” → „gotowe do jazdy”** / **„w drodze”** dopiero po faktycznym wyjeździe?
- Czy dodać akcję **„Wyjechało”** (timestamp startu) między zatwierdzeniem a „Zrealizowane”?
- Jakie **konsekwencje** ma zatwierdzenie dziś: blokada pojazdu, blokada edycji planu, obowiązek wysyłki tego dnia?

**Proponowany przepływ statusów (do weryfikacji):**

| Etap | Co widzi dyspozytor | Co oznacza operacyjnie |
|------|---------------------|-------------------------|
| Propozycja | Solver zaproponował | Do decyzji |
| Gotowe do jazdy / załadowane | Zatwierdzone, czeka na rampie | Auto zajęte, jeszcze nie wyjechało |
| W drodze | Wyjechało (nowe zdarzenie?) | Kierowca w trasie |
| Zrealizowane | Powrót / dostawa zamknięta | Auto wolne, zlecenia zamknięte |

**Oczekiwany efekt:** Dyspozytor wie: (1) kiedy **zatwierdził plan**, (2) kiedy auto **faktycznie ruszyło**, (3) kiedy **wróciło** — bez mylenia „zatwierdzone” z „już jedzie”.

---

## Zakres odpowiedzi

Proszę o:

1. **Krótkie wyjaśnienie obecnego zachowania** (jak jest teraz w aplikacji) — język dla dyspozytora, bez technikaliów.
2. **Propozycję zmian UX** (etykiety, filtry, domyślne widoki).
3. **Propozycję zmian w procesie** (nowe statusy/zdarzenia, np. „Wyjechało”).
4. **Listę decyzji do klienta** (termin z importu vs reguła −2 dni, max czas czekania na dopełnienie).

---

## Powiązane pliki w repozytorium

- `crossdock/ui/pages.py` — widoki Zlecenia, Plan, Magazyn
- `crossdock/services/planning.py` — zatwierdzanie i zamykanie tras
- `crossdock/services/plan_view.py` — etykiety SLA i trasy w drodze
- `crossdock/domain/sla.py` — `must_leave_by`, luz dni
- `docs/jak_planowane_sa_trasy.md` — opis logiki planowania
