# Tydzień 2 — Import + podstawowe ekrany (plan implementacji krok po kroku)

> Daty: **21–27.07.2026** (start możliwy wcześniej po domknięciu T1).
> Harmonogram: [`plan_tworzenia_aplikacji.md`](plan_tworzenia_aplikacji.md) — wiersz T2.
> Powiązane: [`otwarte_wejscia_zespolu.md`](otwarte_wejscia_zespolu.md) (braki od zespołu),
> [`stack_technologiczny.md`](stack_technologiczny.md), [`AGENTS.md`](../AGENTS.md).
>
> **Aktualizacja 20.07.2026:** import i testy oparte na `przykładowe_dane_od_firmy.xlsx`
> (mapowanie e2open w `config/excel_column_mapping.json`). Fixture syntetyczny **usunięty**.

## Cel tygodnia

**„Wgranie prawdziwego pliku → zlecenia w tabeli z filtrami; flota edytowalna w UI”.**

Wariant startowy **bez danych od zespołu** (Patryk / Sandra / Martyna): budujemy pełną
ścieżkę na **placeholderach i seedzie**, z mapowaniem kolumn i flotą w konfiguracji.
Po dostarczeniu danych — podmiana fixture + wpisów w configu, bez przepisywania architektury.
Szczegóły braków: [`otwarte_wejscia_zespolu.md`](otwarte_wejscia_zespolu.md).

## Definicja ukończenia (DoD)

- Upload `.xlsx` w UI → import w tle (`run.io_bound`) → zlecenia w SQLite.
- Raport walidacji per wiersz (odrzucone wiersze z komunikatem po polsku; import nie wywala się na złym wierszu).
- Strona `/orders`: AG Grid z filtrami i sortowaniem; dane z bazy.
- Strona `/settings` (flota): lista pojazdów edytowalna; seed 2–3 typów (bus / ciężarówka / plandeka).
- Port `OrderSource` (Excel) + port `DistanceProvider` (haversine); DataFrame nie wychodzi poza `ingest/`.
- Słownik współrzędnych lokalizacji w bazie + uzupełnianie lat/lon przy imporcie (gdy znane).
- Macierz odległości haversine (numpy) dostępna jako usługa dla przyszłego solvera (T3).
- Testy: parser (happy path + błędy wierszy), FR-024 przy braku daty, haversine smoke, flota CRUD.
- `pre-commit run --all-files` czyste; tag `t2-done`.

## Stan wejściowy po T1

Gotowe: domena `Order`/`Shipment`/`Location`, tabele `orders`/`shipments`, auth, szkielet UI.
Brak: `OrderRepository`, `ingest/`, `distance/`, tabele floty/lokalizacji, mapowanie Excela w configu,
fixtures `.xlsx`, strony `/orders` i `/settings` (placeholdery).

---

## Krok 0 — Notatki i założenia startowe (bez kodu produkcyjnego)

1. Potwierdzić w [`otwarte_wejscia_zespolu.md`](otwarte_wejscia_zespolu.md) listę braków i ownerów.
2. Założyć roboczy format Excela (docelowy wg AGENTS.md: nagłówek w wierszu 3, 45 kolumn e2open) —
   do czasu pliku od Patryka i słownika Sandry używamy **własnego mini-fixture** + mapowania w YAML/TOML.
3. Flota: seed z typowymi pojemnościami (palety + kg) oznaczonymi jako `PLACEHOLDER_PENDING_MARTYNA`.

**Kryterium:** dokumentacja braków zapisana; zespół poinformowany (poza repo).

---

## Krok 1 — Rozszerzenie konfiguracji (mapowanie Excela, progi, ścieżki)

Plik(i) konfiguracyjne — **nie w kodzie**:

- `config/excel_column_mapping.yaml` (lub sekcja w Settings + plik JSON/YAML obok):
  - `header_row` (int, domyślnie 3 dla formatu firmy),
  - mapowanie: `delivery_code`, `shipment_number`, `pickup_*`, `delivery_*`, `weight_kg`,
    `delivery_date`, `equipment_type` → nazwy kolumn w arkuszu,
  - `date_formats` (lista, np. `%m/%d/%Y`),
  - `weight_unit`: `kg` | `lb` (konwersja w ingest),
  - `equipment_aliases`: mapowanie stringów sprzętu (różne między plikami).
- Rozszerzenie `Settings` / osobny loader: ścieżka do mapowania, `min_fill_ratio` (seed pod T3),
  `max_drops_per_route` (seed), współrzędne magazynu (Herentals / okolice Antwerpii) jako depot.

Oznaczyć w pliku mapowania komentarzem: `# TODO: zastąpić słownikiem Sandry (patrz docs/otwarte_wejscia_zespolu.md)`.

**Kryterium:** zmiana nazwy kolumny w YAML zmienia zachowanie parsera bez edycji Pythona.

---

## Krok 2 — Domain: Vehicle + Location dictionary (modele)

W `domain/models.py` (lub `domain/fleet.py`):

- `VehicleType(StrEnum)`: `BUS`, `TRUCK`, `CURTAIN` (plandeka) — nazwy robocze.
- `Vehicle`: `id`, `code`, `vehicle_type`, `pallet_capacity`, `weight_capacity_kg`, `is_active`.
- Opcjonalnie `GeoPoint` / rozszerzenie użycia `Location` ze słownika współrzędnych
  (klucz: znormalizowana nazwa / kod lokalizacji).

Bez logiki solvera — tylko modele pod UI i odległości.

**Kryterium:** modele importowalne; test smoke na walidacji pojemności > 0.

---

## Krok 3 — Storage: migracja Alembic (vehicles, location_coords) + repozytoria

Nowa migracja (wyłącznie Alembic, bez ręcznego schematu):

- `vehicles`: id, code (unique), vehicle_type, pallet_capacity, weight_capacity_kg, is_active, created_at.
- `location_coords`: id, location_key (unique), name, city, country, postal_code, latitude, longitude,
  updated_at — słownik MVP (dziesiątki punktów).
- Ewentualnie kolumny na `orders` już są (pickup/delivery flattened) — bez zmiany, o ile wystarczają.

Repozytoria:

- `OrderRepository`: add_many (transakcja), list (filtry podstawowe), get_by_id; mapowanie ORM ↔ domain.
- `VehicleRepository`: CRUD + list_active.
- `LocationCoordsRepository`: get/upsert/list; lookup po `location_key`.

Seed floty przy starcie (jeśli tabela pusta) — 3 pojazdy placeholder.

**Kryterium:** `alembic upgrade head`; seed widoczny w bazie; testy repo na in-memory SQLite.

---

## Krok 4 — Port `OrderSource` + adapter Excel (`ingest/`)

```
ingest/
  ports.py              # Protocol OrderSource
  excel_import.py       # adapter: ścieżka/bytes → list[Order] + ImportReport
  validation.py         # błędy per wiersz
  row_mapper.py         # wiersz dict → pydantic → Order (FR-024)
```

Zasady (AGENTS.md):

1. pandas czyta arkusz → natychmiast wiersz po wierszu przez pydantic; **DataFrame nie opuszcza `ingest/`**.
2. Błąd jednego wiersza → wpis w `ImportReport` (`row_number`, `message`), reszta idzie dalej.
3. Brak daty dostawy → `Order.create(..., default_delivery_days=settings...)` (FR-024).
4. Brak palet w pliku (znana luka) → `pallet_count=None`; nie wymyślać wartości.
5. Grupowanie: wiele wierszy z tym samym `delivery_code` → jedno `Order` z wieloma `Shipment`
   (nierozdzielność FR-019 na poziomie modelu).

`ImportReport`: `accepted_count`, `rejected: list[RowError]`, `warnings`.

Mini-fixture (wygenerować w kroku 4 lub 5): `tests/fixtures/synthetic_orders_minimal.xlsx`
z kolumnami zgodnymi z roboczym mapowaniem — **nie udawać**, że to plik firmy.

**Kryterium:** testy: 3 poprawne wiersze → N zleceń; 1 zły wiersz → rejected + reszta OK; brak daty → +7 dni.

---

## Krok 5 — Service warstwy: `ImportOrdersService`

`services/import_orders.py`:

- Wejście: ścieżka / upload bytes + username (audyt).
- Wywołuje `OrderSource`, potem `OrderRepository.add_many`, opcjonalnie lookup współrzędnych
  (`LocationCoordsRepository`) i uzupełnienie lat/lon na zamówieniach.
- Zapis `audit_log`: `orders.import` z liczbami accepted/rejected.
- Wywoływane z UI wyłącznie przez `run.io_bound`.

**Kryterium:** test serwisu z fake `OrderSource` + in-memory DB.

---

## Krok 6 — Port `DistanceProvider` + haversine + słownik

```
distance/
  ports.py              # Protocol DistanceProvider
  haversine.py          # straight-line km (numpy)
  matrix.py             # budowa macierzy NxN z listy (lat, lon)
```

- `distance_km(a, b)`; `distance_matrix(points) -> ndarray`.
- Brak I/O w `haversine.py`; odczyt słownika tylko w services/storage.
- UI ustawień: prosta edycja słownika lokalizacji (opcjonalnie w tym samym tygodniu co flota,
  minimum: seed kilku punktów BE + możliwość upsert z poziomu serwisu).

**Kryterium:** test haversine (znana odległość w przybliżeniu, np. Antwerpia–Bruksela ~40–50 km);
macierz symetryczna, diagonal 0.

---

## Krok 7 — UI: import + lista zleceń (`/orders`)

- Usunąć placeholder; dodać:
  - `ui.upload` (.xlsx) + przycisk „Importuj”,
  - pasek / `ui.notify` po zakończeniu (accepted / rejected),
  - dialog lub panel z listą błędów wierszy (po polsku),
  - `ui.aggrid` kolumny: kod dostawy, odbiorca/miasto, termin, status, palety, waga, liczba shipmentów;
    filtry + sortowanie (Community).
- Odświeżanie grida po imporcie.
- Handler uploadu: zapis pliku tymczasowego → `run.io_bound(import_service.run)` → update UI.

**Kryterium:** ręczny flow: upload synthetic fixture → wiersze w gridzie; zły plik → czytelny raport.

---

## Krok 8 — UI: ustawienia floty (`/settings`)

- Tabela / AG Grid pojazdów: kod, typ, pojemność palet, ładowność kg, aktywny.
- Dodaj / edytuj / dezaktywuj (soft).
- Baner lub `ui.label` ostrzegający: wartości tymczasowe do czasu tabeli od Martyny
  (tekst PL + link mentalny do `docs/otwarte_wejscia_zespolu.md`).
- Opcjonalnie zakładka „Słownik lokalizacji” (współrzędne) w tej samej stronie.

**Kryterium:** zmiana pojemności zapisuje się w DB i wraca po restarcie.

---

## Krok 9 — Jakość, fixtures, domknięcie

1. Uzupełnić `tests/fixtures/` (synthetic; README/AGENTS: docelowe pliki firmy — TBD).
2. Testy regresji budżetu: import synthetic &lt; 5 s (smoke).
3. `pre-commit run --all-files`, `pytest --cov`.
4. Walkthrough T2 + tag `t2-done`.
5. Po otrzymaniu danych zespołu: osobny follow-up (nie w DoD T2 bez danych) —
   podmiana mapowania, realny plik, realna flota (checklist w `otwarte_wejscia_zespolu.md`).

---

## Kolejność implementacji (dla AI)

```text
0 docs (otwarte wejścia) 
→ 1 config mapping 
→ 2 domain Vehicle 
→ 3 migracja + repos + seed floty 
→ 4 ingest Excel + synthetic fixture + testy 
→ 5 ImportOrdersService 
→ 6 distance haversine + testy 
→ 7 UI /orders 
→ 8 UI /settings 
→ 9 weryfikacja + tag
```

Nie zaczynać T3 (CP-SAT) w tym tygodniu.

## Ryzyka i mitygacje

| Ryzyko | Mitygacja |
|---|---|
| Format Excela firmy ≠ synthetic | Mapowanie wyłącznie w configu; adapter nie hardcoduje nazw kolumn |
| Brak liczby palet w plikach | `pallet_count=None`; solver T3 musi mieć decyzję (kg vs palety) — patrz otwarte wejścia |
| AG Grid Community vs edycja | Lista zleceń read-only w T2; edycja floty prostymi dialogami NiceGUI jeśli inline będzie kapryśne |
| Duży plik blokuje UI | Zawsze `run.io_bound`; limit rozmiaru uploadu w configu |

## Poza zakresem T2

Solver, mapa Leaflet, raporty, buforowanie, API e2open, OSRM/Photon.
