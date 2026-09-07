# crossdock

System optymalizacji cross-dockingu w logistyce transportowej — aplikacja webowa (local-first, LAN)
dla dyspozytorów: import zleceń transportowych z Excela (docelowo API TMS e2open), automatyczne
planowanie transportów FTL (OR-Tools), wizualizacja tras na mapie, raporty efektywności.

## Struktura

```
crossdock/            # pakiet aplikacji
tests/                # testy + fixtures (.xlsx)
alembic/              # migracje bazy
config/               # mapowania Excel / słowniki
deploy/               # przykłady wdrożenia
scripts/              # skrypty pomocnicze (OSRM)
data/                 # baza SQLite, logi — poza gitem
```

## Uruchomienie

```powershell
uv sync                    # instalacja środowiska z lockfile
mkdir data                 # katalog runtime (baza, logi)
uv run alembic upgrade head
uv run crossdock           # UI: CROSSDOCK_HOST:CROSSDOCK_PORT (domyślnie 0.0.0.0:8080)
```

Sekrety w `.env` (poza gitem); wzorzec w `.env.example`.
`CROSSDOCK_STORAGE_SECRET` jest wymagany; `CROSSDOCK_ADMIN_PASSWORD` tworzy konto `admin` przy pustej bazie.

## Zasady

- Sekrety wyłącznie w `.env` (poza gitem); wzorzec w `.env.example`.
- Zależności tylko przez `uv add` — zmiany w `pyproject.toml` + `uv.lock` razem.
- Przed commitem: `pre-commit run --all-files` (ruff, mypy, import-linter, pytest).
