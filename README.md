# crossdock

System optymalizacji cross-dockingu w logistyce transportowej — aplikacja webowa (local-first, LAN)
dla dyspozytorów: import zleceń transportowych z Excela (docelowo API TMS e2open), automatyczne
planowanie transportów FTL (OR-Tools), wizualizacja tras na mapie, raporty efektywności.

## Dokumentacja

| Plik | Zawartość |
| :--- | :--- |
| **[docs/stan_projektu.md](docs/stan_projektu.md)** | **Aktualny stan (13.08.2026): co działa, czego brak, co dalej** |
| [docs/plan_tworzenia_aplikacji.md](docs/plan_tworzenia_aplikacji.md) | Harmonogram tygodniowy (14.07 → 15.09.2026) |
| [docs/notatka_srs.md](docs/notatka_srs.md) | Wymagania FR / NFR |
| [docs/stack_technologiczny.md](docs/stack_technologiczny.md) | Stack, licencje, decyzje, odrzucone opcje |
| [docs/otwarte_wejscia_zespolu.md](docs/otwarte_wejscia_zespolu.md) | Dane od Patryka / Sandry / Martyny |
| [docs/karta_projektu_i_wdrozenia.md](docs/karta_projektu_i_wdrozenia.md) | Infrastruktura, zespół, fazy wdrożenia |
| [docs/walkthrough_incremental_routes.md](docs/walkthrough_incremental_routes.md) | Scenariusz demo: import tygodnia → zatwierdź trasę |
| [AGENTS.md](AGENTS.md) | Reguły dla agentów AI w tym repo |

Plany i walkthrough T1–T7 w `docs/` to **historia tygodni**, nie bieżący status.

## Struktura

```
crossdock/            # pakiet aplikacji (domain, optimization, ingest, storage, services, ui)
config/               # mapowanie Excela, seed floty, współrzędne
docs/                 # dokumentacja (stan_projektu.md = teraz)
tests/fixtures/       # przykładowe dane z TMS e2open (.xlsx)
dane/                 # robocze pliki z Drive zespołu (nie sekrety)
data/                 # baza SQLite, logi — poza gitem
```

## Uruchomienie

```powershell
uv sync          # instalacja środowiska z lockfile
uv run crossdock # start serwera — UI dostępne w przeglądarce w sieci LAN
```

## Zasady

- Sekrety wyłącznie w `.env` (poza gitem); wzorzec w `.env.example`.
- Zależności tylko przez `uv add` — zmiany w `pyproject.toml` + `uv.lock` razem.
- Przed commitem: `pre-commit run --all-files` (ruff, mypy, import-linter, pytest).
