# Instrukcje dla agentów AI — projekt crossdock

System optymalizacji cross-dockingu w logistyce transportowej. Aplikacja webowa (LAN, local-first)
dla dyspozytorów transportu: import zleceń z Excela (docelowo API TMS e2open), optymalizacja
transportów FTL, wizualizacja tras na mapie, raporty.

**Przed pracą przeczytaj:** `docs/stack_technologiczny.md` (uzgodniony stack i decyzje),
`docs/plan_tworzenia_aplikacji.md` (harmonogram), `docs/notatka_srs.md` (wymagania FR/NFR).

## Stack (nie zmieniaj bez zgody)

- Python 3.12+, zarządzanie: **uv** (`uv sync`, `uv add`), definicja w `pyproject.toml`
- UI: **NiceGUI** (mapa: `ui.leaflet`, tabele: `ui.aggrid`, wykresy: `ui.echart`)
- Baza: **SQLite** (tryb WAL) + **SQLAlchemy 2.0** + migracje **Alembic**
- Optymalizacja: **OR-Tools** (CP-SAT + Routing Solver)
- Walidacja: **pydantic v2**; konfiguracja/sekrety: **pydantic-settings** + `.env`
- Import/raporty: **pandas** + **openpyxl**; HTTP: **httpx**; harmonogram: **APScheduler**
- Logi: **loguru** (`enqueue=True`); hasła: **argon2-cffi**
- Testy: **pytest** + **hypothesis**; lint/format: **ruff**; typy: **mypy**; architektura: **import-linter**

## Architektura (twarde reguły)

Struktura pakietu `crossdock/`:
`domain/` (modele + niezmienniki), `optimization/` (czysty solver), `distance/` (port DistanceProvider),
`ingest/` (port OrderSource), `storage/` (repozytoria), `services/` (przypadki użycia), `ui/` (strony NiceGUI).

1. Kierunek zależności: `ui -> services -> domain/optimization`. NIGDY odwrotnie.
2. `optimization/` NIE importuje niczego z I/O (ui, storage, ingest, httpx, pandas).
   Wejście/wyjście solvera = proste, serializowalne dataclasses (przechodzą przez pickle między procesami).
3. Porty (`OrderSource`, `DistanceProvider`) jako `Protocol`/ABC z wymiennymi adapterami.
   Faza 1: Excel + haversine (linia prosta). Faza 2: API e2open + OSRM. Nie mieszaj implementacji z portem.
4. Dane z pandas natychmiast przechodzą przez modele pydantic — DataFrame nie wychodzi poza `ingest/`.
5. Reguła nierozdzielności przesyłek (FR-019: shipmenty spięte pod jednym zleceniem jadą zawsze razem)
   to niezmiennik w `domain/` — egzekwowany i w solverze, i przy edycji ręcznej.

## Płynność (wymaganie projektowe, nie dodatek)

- Solver ZAWSZE przez `run.cpu_bound()` NiceGUI (osobny proces). Nigdy w pętli zdarzeń.
- Import Excela, geokodowanie, eksporty: `run.io_bound()` lub async httpx.
- Żaden handler UI nie liczy dłużej niż ~50 ms.
- Solver: twardy limit czasu (30–60 s) + stały seed (powtarzalność wyników).
- Do solvera przekazuj tylko liczby i identyfikatory (lekkie DTO), nie obiekty ORM.

## Konwencje

- Kod, nazwy, komentarze: **angielski**. Teksty w UI (etykiety, komunikaty): **polski**.
- Nowe zależności: NIE dodawaj bez wyraźnej zgody użytkownika. Preferuj stdlib.
- Mapowanie kolumn Excela i progi biznesowe (min. zapełnienie, maks. liczba dropów, próg buforowania,
  stawki kosztowe) trzymaj w konfiguracji, nie w kodzie.
- Sekrety wyłącznie w `.env` (jest w .gitignore); w repo tylko `.env.example`. Nigdy nie commituj
  haseł, kluczy API ani danych dostępowych do TMS e2open.
- Migracje bazy wyłącznie przez Alembica — bez ręcznych zmian schematu.
- Testy: reguły domenowe i niezmienniki solvera mają testy ZAWSZE (pytest + hypothesis);
  budżety wydajności z planu jako testy regresyjne.

## Dane testowe

`tests/fixtures/przykladowe_dane_od_firmy.xlsx` — bogaty raport e2open (45 kolumn, nagłówek w wierszu 3,
wiersz 1 to metadane; rozbite adresy miasto/kraj/kod, wagi w kg, daty MM/DD/YYYY jako tekst).
To DOCELOWY format importu.

`tests/fixtures/przykladowe_dane_wygenerowane_z_systemu_TMS.xlsx` — okrojony raport (25 kolumn,
nagłówek w wierszu 1; adres tylko nazwą odbiorcy, wagi w FUNTACH, objętość w stopach szesciennych).

Uwaga: żaden plik nie zawiera liczby palet (wymaganie FR-004) — kwestia otwarta, wyjaśniana z firmą.
Słowniki sprzętu różnią się między plikami ("Flatbed" vs "EU: 09 CURTAIN / BOX TRAILER") — mapuj przez konfigurację.
