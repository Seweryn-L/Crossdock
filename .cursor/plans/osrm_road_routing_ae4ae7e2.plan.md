---
name: OSRM road routing
overview: "Szczegółowy plan dodania OSRM: solver liczy po odległościach drogowych, a mapa rysuje geometrie dróg (nie linie proste). Integracja robiona lokalnie z OSRM w Dockerze i datasetem dla Belgii."
todos:
  - id: osrm-docker-local
    content: Dodać lokalny `docker-compose`/profile z kontenerem `osrm` (endpoint `:5000`) oraz przygotować dataset Belgii (wariant A/B). Ustawić env `CROSSDOCK_USE_OSRM` i `CROSSDOCK_OSRM_URL`.
    status: pending
  - id: osrm-distance-provider
    content: Implementować klient OSRM w `crossdock/distance/` do `table` (DistanceProvider.distance_matrix) + cache.
    status: pending
  - id: planning-pipeline-refactor
    content: "Przerobić `crossdock/services/planning.py` tak, aby `run.cpu_bound` nie robił I/O: split na cpu_bound `solve_assignment` + io_bound budowę routing inputs z OSRM table + cpu_bound `solve_routes`."
    status: pending
  - id: map-osrm-geometry
    content: Zaktualizować `crossdock/services/map_view.py`, aby w trybie OSRM pobierał geometrię `/route` i ustawiał `VehicleMapRoute.polyline` na faktyczną drogę (fallback do haversine path).
    status: pending
  - id: settings-and-flags
    content: Dodać do `crossdock/config.py` flagi i pola ustawień dla OSRM (URL, profile, enable).
    status: pending
  - id: tests-osrm-mocks
    content: Dodać testy z mockiem httpx dla OSRM table/route oraz testy `MapViewService` i routing inputs, bez potrzeby prawdziwego OSRM w CI.
    status: pending
  - id: smoke-local
    content: "Wykonać lokalny smoke test: import fixture → generuj plan → mapa pokazuje drogi; porównać zmiany vs haversine."
    status: pending
isProject: false
---

# OSRM road routing — plan szczegółowy (lokalnie)

## Cel

1. Zastąpić w planowaniu odległości „haversine” odległościami drogowymi z OSRM, tak aby **kolejność dropów i koszt/kilometry** były zgodne z drogami.
2. Na ekranie `[/map]` rysować **geometrię prawdziwych dróg** (polilinia z OSRM), a nie proste odcinki między punktami.

## Aktualny stan w kodzie (punkt wyjścia)

- Solver do routingu używa `HaversineDistanceProvider()` w `crossdock/services/planning.py` (w `solve_prepared_plan`):
  - `distance = HaversineDistanceProvider()` (obecnie zawsze).
  - Następnie `_build_routing_inputs(...)` buduje `distance_matrix_m` z odległości liniowych.
- Mapa rysuje proste linie między kolejnymi przystankami:
  - `crossdock/services/map_view.py` buduje `polyline=tuple(path)` gdzie `path` to tylko `[depot] + [lat/lon dropów w sequence]`.
  - `crossdock/ui/pages.py` na `page('/map')` używa `route.polyline` do Leaflet `polyline`.

## Wymagania architektoniczne (ważne)

- `run.cpu_bound(...)` (proces OR-Tools) nie może wykonywać wywołań I/O (OSRM HTTP).
- OSRM HTTP robimy w ścieżkach `run.io_bound(...)` (albo przed wejściem do cpu_bound), aby nie psuć izolacji procesu solvera.

## Proponowana architektura zmian

```mermaid
flowchart LR
  UI[UI: /plans "Generuj" / /map] --> P1[PlanningService przygotowuje PlanSolveRequest]
  P1 --> C1[cpu_bound: solve_assignment (CP-SAT) — bez OSRM]
  C1 --> IO1[io_bound: budowa routing inputs z OSRM table/distance_matrix]
  IO1 --> C2[cpu_bound: solve_routes (OR-Tools routing) — czyste matrix_m]
  C2 --> Persist[Persist planu do SQLite]
  Persist --> IO2[io_bound: MapViewService z OSRM /route — geometria polilinii]
  IO2 --> MapUI[/map Leaflet polyline + arrows]
```



## Plan wdrożenia — kroki implementacyjne

### Krok 0: Lokalny OSRM w Dockerze + dataset Belgii

Ponieważ wybraliście wariant `need_download`, plan zawiera instrukcję zdobycia datasetu.

#### 0.1 Co musimy mieć

- OSRM endpoint dostępny w sieci dockera (np. `http://osrm:5000`).
- Przygotowany preprocessed plik/directory: `*.osrm` dla Belgii.

#### 0.2 Warianty datasetu (A/B)

- **A (preferowane):** pobierz gotowe preprocessed pliki dla Belgii (jeśli znajdziecie gotowy artefakt).
- **B:** self-preprocess z OSM PBF dla Belgii:
  1. pobierz `planet/region .pbf` (np. Geofabrik/BBBike — wg wyboru),
  2. odpal `osrm-extract`, `osrm-contract`, `osrm-routed` w kontenerze (albo na hoście).

#### 0.3 docker-compose lokalnie

Dopisz lokalnie serwis `osrm` (osrm-backend) i mount pointy pod dane OSRM oraz ewentualnie port `5000` (dla debugowania).

**Wymagane zmienne dla aplikacji**:

- `CROSSDOCK_USE_OSRM=true`
- `CROSSDOCK_OSRM_URL=http://osrm:5000`
- `CROSSDOCK_OSRM_PROFILE=driving`

Uwaga: w tej fazie nie zmieniamy docelowego deployu na VM, tylko robimy lokalny setup.

### Krok 1: OSRM DistanceProvider (dla matrix) — warstwa `crossdock/distance/`

#### 1.1 Nowy adapter

Dodaj nową klasę (np. `OsrmDistanceProvider`) realizującą `DistanceProvider`:

- `distance_matrix(points)`:
  - użyć OSRM `table` API: `/table/v1/{profile}/{lon,lat;...}?annotations=distance`
  - zamienić metry → kilometry.
- `distance_km(...)`:
  - (opcjonalnie) pobieraj z `table` dla dwóch punktów, albo z osobnego endpointu.

#### 1.2 Cache

Dodaj prosty cache w obrębie procesu (np. LRU) dla:

- macierzy dystansów dla identycznych list punktów,
- geometrii tras dla identycznych sekwencji waypointów.

### Krok 2: Refactor pipeline planowania (żeby solver był nadal cpu_bound-only)

#### 2.1 Rozdzielenie `solve_prepared_plan`

Dziś `crossdock/services/planning.py: solve_prepared_plan` robi:

- assignment + routing, gdzie routing inputs budowane są w `_build_routing_inputs` przy użyciu `HaversineDistanceProvider`.

Zmieniamy pipeline na:

1. `cpu_bound`: `solve_assignment` → zwraca `AssignmentResult` (bez OSRM)
2. `io_bound`: budowa `routing_inputs`:
  - grupowanie drop nodes (logika z `_build_routing_inputs`)
  - dla każdego `points` zestawu: odpal OSRM table → `distance_matrix_m`
3. `cpu_bound`: `solve_routes(RoutingRequest(...distance_matrix_m...))`
4. pure mapping: wyliczenie `sequence_by_order`, `items` i `routes_payload` (jak obecnie)
5. persist planu jak dotychczas

#### 2.2 Miejsca w kodzie do zmiany

- `crossdock/services/planning.py`
  - nowa funkcja `solve_prepared_plan_osrm(...)` albo rozbicie `solve_prepared_plan` na mniejsze prywatne helpers.
- `crossdock/ui/pages.py`
  - w `on_generate()` trzeba wziąć pod uwagę, że zamiast 1 cpu_bound będą 2 cpu_bound z 1 io_bound w środku.
  - UX/progress może zostać podobny (np. jedno „Optymalizacja” obejmujące cały proces).

### Krok 3: Mapa z geometrią dróg (OSRM /route)

#### 3.1 Zmiana MapViewService

W `crossdock/services/map_view.py`:

- aktualnie `polyline=tuple(path)`.
- dodaj tryb `use_osrm_geometry`:
  - buduj waypointy w kolejności: `depot -> drop1 -> drop2 -> ... -> depot`
  - wywołaj OSRM `/route/v1/{profile}/{lon,lat;...}` z parametrami:
    - `overview=full`
    - `geometries=geojson`
  - zamień `geojson.coordinates` (lon,lat) → lista (lat,lon)
  - ustaw `polyline` tą listą

#### 3.2 Fallback

Jeśli OSRM nie odpowie lub brakuje współrzędnych:

- fallback do obecnego `path` (linie proste), żeby UI zawsze działało.

### Krok 4: Testy i walidacja

#### 4.1 Testy jednostkowe OSRM klienta

- Mock httpx (np. `httpx.MockTransport`) dla:
  - `table` → sprawdź parsowanie dystansów w `distance_matrix`.
  - `route` → sprawdź parsowanie geometrii.

#### 4.2 Testy map view

- Dodaj testy dla `MapViewService` w trybie `use_osrm_geometry=False` (żeby nie naruszyć istniejących oczekiwań).
- Dodaj testy dla `use_osrm_geometry=True` na mocked OSRM endpoint.

#### 4.3 Testy planowania

- Nie próbujemy w testach robić realnego OSRM.
- W testach upewniamy się, że przy włączonym OSRM routing solver dostaje `distance_matrix_m` zamiast haversine.

### Krok 5: UX i wydajność

- Ze względu na to, że `max_drops_per_route` jest małe (domyślnie 3), liczba waypointów na route jest niska.
- Mimo to dodaj caching, aby /map nie waliło w OSRM przy każdym odświeżeniu.

---

## Co dostaniesz po wdrożeniu (weryfikacja)

1. `Plany -> Generuj plan` zmienia kolejność dropów i koszty (vs haversine), bo solver używa road distances.
2. `Mapa` pokazuje polilinie zgodne z drogami (geometria z OSRM), a strzałki obracają się zgodnie z przebiegiem drogi.

---

## Lista plików (najważniejsze)

- `crossdock/services/planning.py` (split cpu_bound/io_bound + OSRM matrix)
- `crossdock/distance/haversine.py` (baseline) oraz nowe `crossdock/distance/osrm_*.py`
- `crossdock/services/map_view.py` (OSRM geometry)
- `crossdock/ui/pages.py` (progress i tryb nawigacji mapy)
- `crossdock/config.py` (flagi i URL OSRM)
- `tests/` (mock OSRM + testy map view / routing inputs)

---

## Ustalenie kolejności pracy lokalnie

1. OSRM setup w Dockerze + dataset (A/B)
2. klient OSRM w `crossdock/distance/`
3. refactor planowania (split pipeline)
4. geometria w `/map`
5. testy + smoke test na fixture e2open

