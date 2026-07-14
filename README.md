# crossdock

System optymalizacji cross-dockingu w logistyce transportowej — aplikacja webowa (local-first, LAN)
dla dyspozytorów: import zleceń transportowych z Excela (docelowo API TMS e2open), automatyczne
planowanie transportów FTL (OR-Tools), wizualizacja tras na mapie, raporty efektywności.

## Dokumentacja

| Plik | Zawartość |
| :--- | :--- |
| [docs/stack_technologiczny.md](docs/stack_technologiczny.md) | Uzgodniony stack: technologie, licencje, decyzje architektoniczne, odrzucone opcje |
| [docs/plan_tworzenia_aplikacji.md](docs/plan_tworzenia_aplikacji.md) | Harmonogram tygodniowy (14.07 → 15.09.2026) z kamieniami milowymi |
| [docs/notatka_srs.md](docs/notatka_srs.md) | Wymagania funkcjonalne (FR) i niefunkcjonalne (NFR) |
| [docs/karta_projektu_i_wdrozenia.md](docs/karta_projektu_i_wdrozenia.md) | Karta projektu: infrastruktura, zespół, fazy wdrożenia |
| [AGENTS.md](AGENTS.md) | Reguły dla agentów AI piszących kod w tym repozytorium |

## Struktura

```
crossdock/            # pakiet aplikacji (powstanie w T1 planu)
docs/                 # dokumentacja projektowa (kopie robocze)
tests/fixtures/       # przykładowe dane z TMS e2open (.xlsx)
data/                 # baza SQLite, logi — poza gitem
```

## Uruchomienie (od T1)

```powershell
uv sync          # instalacja środowiska z lockfile
uv run crossdock # start serwera — UI dostępne w przeglądarce w sieci LAN
```

## Zasady

- Sekrety wyłącznie w `.env` (poza gitem); wzorzec w `.env.example`.
- Zależności tylko przez `uv add` — zmiany w `pyproject.toml` + `uv.lock` razem.
- Przed commitem: `pre-commit run --all-files` (ruff, mypy, import-linter, pytest).
