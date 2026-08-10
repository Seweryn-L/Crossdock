# Tydzień 1 — Walkthrough (Kroki 7–8)

## Wykonane prace

### Krok 7 — Jakość: ruff, mypy, import-linter, pre-commit

Konfiguracja jakości była już częściowo przygotowana w krokach 0–6. W kroku 7 doprowadzono do stanu, w którym `pre-commit run --all-files` przechodzi czysto.

#### Konfiguracja narzędzi (już obecna w `pyproject.toml`)
- **ruff**: lint + format, `target-version = "py312"`, `line-length = 100`, `extend-exclude = ["alembic/versions"]`
- **mypy**: `strict = true`, ograniczony do `crossdock/domain` i `crossdock/services`
- **import-linter** (`.importlinter`): 3 kontrakty:
  - `layers`: `ui → services → domain`
  - `optimization-purity`: optimization nie importuje ui/storage/ingest/httpx/pandas/nicegui/sqlalchemy
  - `domain-purity`: domain nie importuje żadnej innej warstwy crossdock

#### Poprawki wprowadzone
1. **`.pre-commit-config.yaml`** — zmieniono `entry` hooków z `uv run <tool>` na `uv run <tool>` z `--force-exclude` dla ruff (aby `extend-exclude` z pyproject.toml było respektowane gdy pre-commit podaje pliki jawnie)
2. **`.gitignore`** — dodano `.import_linter_cache/`, `.hypothesis/`, `.nicegui/`

#### Wynik `pre-commit run --all-files`
```
ruff (lint)..............................................................Passed
ruff (format)............................................................Passed
mypy (domain + services).................................................Passed
import-linter (architektura warstw)......................................Passed
pytest (szybkie testy)...................................................Passed
```

---

### Krok 8 — Weryfikacja end-to-end

#### 1. Pytest z coverage
```
31 passed in 2.59s

Name                                 Stmts   Miss  Cover
------------------------------------------------------------------
crossdock/domain/models.py              67      1    99%
crossdock/services/auth.py              43      1    98%
crossdock/storage/tables.py             49      0   100%
crossdock/storage/repositories.py       38      3    92%
------------------------------------------------------------------
TOTAL                                  402    167    58%
```
- Domena i serwisy: 98–100% pokrycia
- UI: 0% (wymaga testów integracyjnych z przeglądarką — poza zakresem T1)

#### 2. Alembic upgrade head
```
INFO  [alembic.runtime.migration] Running upgrade  -> 38bf6baa23f9, initial schema
```
Tabele w bazie: `alembic_version`, `audit_log`, `orders`, `shipments`, `users` ✅

#### 3. Start serwera
```
Utworzono startowe konto administratora 'admin'.
Start serwera Crossdock na 0.0.0.0:8080
NiceGUI ready to go on http://localhost:8080, http://192.168.0.38:8080, ...
```
Serwer nasłuchuje na LAN (0.0.0.0:8080) ✅

#### 4. Test w przeglądarce (nagrania)
Przeprowadzono pełny test flow:

1. **Redirect** — wejście na `/` przekierowuje na `/login?redirect_to=/` ✅
2. **Strona logowania** — wyświetla: "Crossdock", "System optymalizacji cross-dockingu", pola "Nazwa użytkownika" / "Hasło", przycisk "Zaloguj się" ✅
3. **Błędne dane** — powiadomienie "Nieprawidłowa nazwa użytkownika lub hasło" ✅
4. **Poprawne logowanie** (admin) — redirect na pulpit ✅
5. **Pulpit** — "Witaj w systemie Crossdock", status "Brak zaimportowanych zleceń" ✅
6. **Nawigacja** — menu boczne: Pulpit, Zlecenia, Plany, Mapa, Raporty, Ustawienia ✅
7. **Placeholder** — strona "Zlecenia" z "W przygotowaniu" ✅
8. **Wylogowanie** — "Wyloguj" czyści sesję, redirect na `/login` ✅

#### 5. Git commit + tag
```
ed283f2 (HEAD -> master, tag: t1-done) feat(t1): complete week 1 foundation
d25371a docs: initial project documentation
```

---

## Definicja ukończenia T1 — status

| Kryterium | Status |
|---|---|
| `uv sync` odtwarza środowisko | ✅ |
| `uv run crossdock` startuje NiceGUI w LAN | ✅ |
| Wejście bez sesji → redirect na `/login` | ✅ |
| Logowanie argon2 otwiera pulpit | ✅ |
| Wylogowanie czyści sesję | ✅ |
| Role admin/dispatcher/viewer w SQLite | ✅ |
| Schemat przez migrację Alembica | ✅ |
| Admin startowy tworzony seedem | ✅ |
| `pytest` — zielone testy FR-019 i FR-024 | ✅ (31 testów) |
| `pre-commit run --all-files` czyste | ✅ (5 hooków) |
| import-linter: `ui → services → domain` | ✅ (3 kontrakty) |
| Tag `t1-done` | ✅ |

> [!NOTE]
> Pre-commit hooks wymagają `uv` na PATH. Przy `git commit` ścieżka `~/.local/bin` musi być w PATH
> (w sesji PowerShell: `$env:PATH = "$env:USERPROFILE\.local\bin;$env:PATH"`).
