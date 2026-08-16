# Stack technologiczny — System optymalizacji cross-dockingu w logistyce transportowej

> Opracowano na podstawie: `karta_projektu_i_wdrozenia.md`, `notatka_srs.md` oraz decyzji podjętych w rozmowie (14.07.2026).
> Stan implementacji na 13.08.2026: [`stan_projektu.md`](stan_projektu.md).
> Zasady nadrzędne: rdzeń w Pythonie, w pełni local-first (bez komponentów chmurowych — decyzja z Obszaru 13),
> wyłącznie oprogramowanie darmowe/open-source, płynność jako wymaganie projektowe.

---

## 1. Podsumowanie stacku

| Warstwa | Technologia | Licencja |
| :--- | :--- | :--- |
| Interfejs użytkownika | NiceGUI (web, LAN) + wbudowane: Leaflet, AG Grid Community, ECharts | MIT / BSD-2 / MIT / Apache-2.0 |
| Architektura | Monolit modularny, warstwy + porty/adaptery (`OrderSource`, `DistanceProvider`) | — (wzorzec) |
| Rdzeń optymalizacji | Google OR-Tools (CP-SAT + Routing Solver); heurystyka kosztowa buforowania w czystym Pythonie | Apache-2.0 |
| Przetwarzanie danych | pandas + openpyxl (import Excel, raporty .xlsx/.csv) + pydantic (walidacja) | BSD-3 / MIT / MIT |
| Przechowywanie danych | SQLite (WAL) + SQLAlchemy 2.0 + Alembic | Public domain / MIT / MIT |
| Komunikacja i integracje | httpx, APScheduler (w procesie), OSRM self-hosted (Faza 2), geopy + self-hosted Photon | BSD-3 / MIT / BSD-2 / MIT + Apache-2.0 |
| Wydajność | asyncio (pętla UI) + `run.cpu_bound` (solver w osobnym procesie) + `run.io_bound`; py-spy do profilowania | PSF / MIT |
| Bezpieczeństwo | pydantic-settings + `.env`, argon2-cffi, role w modelu od startu, HTTP w zaufanym LAN | MIT / MIT |
| Testy i jakość | pytest, hypothesis, ruff, mypy, import-linter, pre-commit | MIT / MPL-2.0 (dev) / MIT / MIT / BSD-2 / MIT |
| Środowisko dev | uv + pyproject.toml + lockfile, CPython 3.12/3.13, git lokalny | MIT+Apache-2.0 / — / GPL-2.0 (narzędzie) |
| Pakowanie i dystrybucja | Bez binarki: kopia kodu + `uv sync` + Harmonogram zadań Windows; klient = przeglądarka | — |
| Logi, monitoring, błędy | loguru (rotacja), audyt biznesowy w SQLite, strona "Stan systemu", backup przez sqlite3 backup API | MIT / — / — / PSF |
| Komponenty chmurowe | **Brak — decyzja projektowa** | — |

Usługi lokalne poza pip (stawiane obok aplikacji, gdy staną się potrzebne): **OSRM** (routing drogowy, Docker, Faza 2),
**Photon** (geokodowanie), **Protomaps/PMTiles** (podkład mapy z lokalnego serwera).

---

## 2. Szczegóły obszarów

### Obszar 1: Warstwa interfejsu użytkownika

**Rekomendacja:** NiceGUI — panel dyspozytora w czystym Pythonie, dostęp przeglądarką w sieci LAN.

**Dlaczego:** Jeden programista w zespole → brak osobnego frontendu JS. Wbudowana mapa Leaflet (FR-016),
tabele AG Grid z edycją inline (FR-020/021), wykresy ECharts (FR-017/018). Natywna obsługa wielu równoczesnych
sesji (wymóg: kilku użytkowników). Web zamiast desktopu: jedna instalacja, jedna baza, zero dystrybucji na stanowiska.

**Wpływ na płynność:** Aktualizacje po WebSocket (częściowe zmiany DOM, milisekundy w LAN);
warunek: solver nigdy w pętli zdarzeń (→ Obszar 7).

**Ryzyka:** Mniejsza społeczność niż React; stan sesji w pamięci serwera (przy kilku użytkownikach pomijalne);
mocno customowe widoki trudniejsze niż w czystym JS.

| Biblioteka | Rola w projekcie | Licencja | Dojrzałość |
| :--- | :--- | :--- | :--- |
| nicegui | Cały UI: pulpit, mapa, kolejka magazynu, zatwierdzanie planów, raporty, ustawienia floty | MIT | v3.14.0 (06.2026), bardzo aktywna |
| Leaflet / AG Grid Community / ECharts | Mapa tras / tabele zleceń z edycją / wykresy raportów — wbudowane w NiceGUI, bez osobnej instalacji | BSD-2 / MIT / Apache-2.0 | standardy branżowe |

### Obszar 2: Architektura i struktura projektu

**Rekomendacja:** Monolit modularny: `domain / optimization / distance / ingest / storage / services / ui`.
Porty z wymiennymi adapterami **tylko** tam, gdzie plan przewiduje wymianę: `OrderSource` (Excel → API e2open)
i `DistanceProvider` (haversine → OSRM). Reguła zależności: `ui → services → domain/optimization`;
`optimization` bez żadnego I/O.

```
crossdock/
├── domain/           # Modele biznesowe + niezmienniki (np. nierozdzielność shipmentów, FR-019)
├── optimization/     # CZYSTY rdzeń: grupowanie cross-dock, pakowanie FTL, decyzja "wyślij vs buforuj"
├── distance/         # Port DistanceProvider: straight_line.py (Faza 1) / road_network.py (OSRM)
├── ingest/           # Port OrderSource: excel_import.py (Faza 1) / e2open_api.py (Faza 2)
├── storage/          # Repozytoria (SQLite przez SQLAlchemy)
├── services/         # Przypadki użycia: import, generuj plan, zatwierdź, zmień palety, rotuj kolejkę
├── ui/               # Strony NiceGUI
└── config.py         # Konfiguracja (parametry kosztowe, progi zapełnienia, mapowanie kolumn Excela)
```

**Dlaczego:** Dwufazowy plan wdrożenia + decyzja o docelowych trasach realnych wyznaczają dokładnie dwa punkty
wymiany. Czysty, serializowalny rdzeń `optimization` to warunek techniczny uruchamiania solvera w osobnym procesie.
Niezmiennik FR-019 w `domain` — pilnowany i przez solver, i przez edycję ręczną.

**Wpływ na płynność:** Zerowy koszt wykonania; umożliwia nieblokujący solver i importy w tle.

**Ryzyka:** Przedwczesna abstrakcja (porty tylko dla 2 wymian); erozja reguł zależności — pilnuje import-linter.

| Biblioteka | Rola w projekcie | Licencja |
| :--- | :--- | :--- |
| pydantic v2 | Modele z walidacją na granicach: wiersze Excela, przyszłe API, konfiguracja | MIT |
| stdlib `abc`/`Protocol`, `dataclasses` | Definicje portów; lekkie DTO wejścia/wyjścia solvera (pickle między procesami) | PSF |

### Obszar 3: Rdzeń logiki biznesowej

**Rekomendacja:** OR-Tools — CP-SAT (przydział przesyłek do pojazdów: pojemności, nierozdzielność FR-019)
+ Routing Solver (kolejność dropów, limit 3 punktów FR-012, minimalizacja km FR-014).
Buforowanie FR-022 = prosta reguła kosztowa w Pythonie na modelu kosztowym (decyzja: to dodatek, nie rdzeń).
Flota stała, edytowalna w ustawieniach (tabela w bazie + ekran UI) — bez decyzji "ile pojazdów wynająć".

**Dlaczego:** Problem to bin packing + VRP z ograniczeniami, które OR-Tools ma wbudowane; przy skali dziesiątek
zleceń dobre rozwiązania w sekundach. Macierz odległości jako wejście → podmiana linia prosta/trasy realne
nie dotyka solvera.

**Wpływ na płynność:** Solver anytime z twardym limitem 30–60 s + seed dla powtarzalności; zawsze w osobnym procesie.

**Ryzyka:** Krzywa uczenia modelowania ograniczeń (1–2 tyg. na prototyp); dokumentacja Routing Solvera wyrywkowa.

| Biblioteka | Rola w projekcie | Licencja | Dojrzałość |
| :--- | :--- | :--- | :--- |
| ortools | Silnik optymalizacji FR-009…FR-014, FR-019 | Apache-2.0 | Google, aktywna [wersję przypiąć przy inicjalizacji] |
| numpy | Wektorowa macierz haversine; rachunki wskaźników zapełnienia | BSD-3 | fundament ekosystemu |

### Obszar 4: Przetwarzanie i analiza danych

**Rekomendacja:** pandas (silnik openpyxl) do importu i agregacji raportowych; każdy wiersz natychmiast przez
pydantic — dalej w systemie żyją tylko obiekty domenowe. Raporty: eksport .xlsx/.csv (decyzja: PDF niepotrzebny).

**Dlaczego:** Plik przygotowywany ręcznie będzie niedoskonały → walidacja wiersz-po-wierszu z raportem błędów
("wiersz 14: brak palet") zamiast wywałki importu. Mapowanie kolumn w konfiguracji, nie w kodzie
(format e2open jeszcze nieustalony).

**Wpływ na płynność:** Import w tle (`run.io_bound`); koszt pandas (import ~1–2 s, ~100 MB RAM) jednorazowy
przy starcie serwera.

**Ryzyka:** Nieustalony format pliku e2open — parser defensywny; zakaz przekazywania DataFrame'ów w głąb systemu.

| Biblioteka | Rola w projekcie | Licencja |
| :--- | :--- | :--- |
| pandas | Odczyt arkusza e2open; agregacje raportów (oszczędności/trasa, zapełnienie/pojazd); eksport .xlsx | BSD-3 |
| openpyxl | Silnik .xlsx; formatowanie eksportu (nagłówki, kolory progów) | MIT |

### Obszar 5: Przechowywanie danych

**Rekomendacja:** SQLite (WAL + `busy_timeout`) + SQLAlchemy 2.0 + Alembic. Tabele: zlecenia+shipmenty
(relacja nierozdzielności), flota, plany (FR-023: gotowe 4–5 dni przed wysyłką), kolejka magazynowa,
audyt (FR-020/021), cache geokodowania, użytkownicy z rolami.

**Dlaczego:** Serwer na zwykłym PC → baza w procesie, zero administracji, backup = kopia pliku.
Kilku użytkowników przechodzi przez jeden proces serwera → model współbieżności SQLite w pełni bezpieczny.
Wolumen: dziesiątki tysięcy wierszy rocznie.

**Wpływ na płynność:** Odczyty mikrosekundowe (bez sieci); operacje masowe w jednej transakcji i w tle;
świadomie sync-SQLAlchemy (async bez mierzalnego zysku przy tej skali).

**Ryzyka:** Jeden piszący proces — scheduler musi żyć w procesie serwera (tak zaplanowano);
dysk pojedynczego PC → backup obowiązkowy (Obszar 12). Migracja na PostgreSQL w razie wzrostu = zmiana
connection stringa dzięki SQLAlchemy.

| Biblioteka | Rola w projekcie | Licencja |
| :--- | :--- | :--- |
| SQLite / stdlib `sqlite3` | Cała trwałość danych systemu | Public domain |
| SQLAlchemy 2.0 | Mapowanie domeny na tabele, transakcje, przenośność | MIT |
| Alembic | Wersjonowane migracje między fazami (pola API, GPS) z backupem przed migracją | MIT |

### Obszar 6: Komunikacja i integracje

**Rekomendacja:**
- **httpx** — async klient HTTP (przyszłe API e2open, OSRM, Photon).
- **Geokodowanie lokalne:** w MVP słownik współrzędnych lokalizacji utrzymywany w aplikacji (skala: dziesiątki
  punktów), docelowo self-hosted **Photon** za adapterem + trwały cache w SQLite.
- **Trasy realne: self-hosted OSRM** (Docker; zaakceptowany, gdy stanie się konieczny — Belgia + kraje ościenne,
  graf kilka GB RAM) — usługa `table` (macierz dla OR-Tools) i `route` (geometrie na mapę).
- **APScheduler w procesie serwera** dla okien 5:30–6:00 / 11:30–12:00 (NFR-001; w MVP ten sam kod pod przyciskiem).
- Kolejek komunikatów i IPC brak — nie dotyczy tego projektu.

**Wpływ na płynność:** Wszystkie wywołania zewnętrzne async/w tle; macierz z lokalnego OSRM w milisekundach;
import o 5:30 przed godzinami pracy.

**Ryzyka:** Format API e2open i źródło GPS = niewiadome blokujące (zaprojektowane porty, nie implementacje);
OSRM liczy profil samochodowy — jeśli potrzebne restrykcje ciężarówkowe, kandydatem Valhalla (MIT);
dane OSM odświeżać co kilka miesięcy.

| Biblioteka | Rola w projekcie | Licencja | Dojrzałość |
| :--- | :--- | :--- | :--- |
| httpx | Async HTTP: e2open API (Faza 2), OSRM, Photon | BSD-3 | aktywna |
| geopy | Adapter geokodera (klasa Photon — działa z self-hosted) | MIT | stabilna [aktywność do weryfikacji] |
| APScheduler | Okna importu + zadania porządkowe, w procesie serwera | MIT | dojrzała |
| OSRM (usługa) | Lokalna macierz odległości drogowych + geometrie tras | BSD-2 | bardzo dojrzała |
| Photon (usługa) | Lokalne geokodowanie adresów, gdy słownik przestanie wystarczać | Apache-2.0 | utrzymywana [do weryfikacji] |

### Obszar 7: Wydajność i płynność

**Rekomendacja:** Trójwarstwowy model wykonania: pętla asyncio wyłącznie dla interakcji (żadna funkcja handlera
> ~50 ms); solver przez `run.cpu_bound` (pula procesów, osobny GIL, postęp na żywo z callbacków CP-SAT);
I/O przez `run.io_bound`/async httpx. **Bez własnych rozszerzeń kompilowanych** — ciężka praca już jest
w C++/C/Rust (ortools, numpy, sqlite, pydantic-core). Najnowszy stabilny CPython.

**Budżety wydajności (przyjęte jako wymagania):**
- interakcje UI: < 100 ms,
- import Excela z walidacją: < 5 s (w tle, z paskiem postępu),
- generowanie planu: twardy limit solvera 30–60 s (anytime — po limicie najlepsze znalezione rozwiązanie),
- RAM aplikacji: ~300–500 MB (+ kilka GB dla OSRM, gdy dojdzie).

**Ryzyka:** Rozdęte DTO między procesami (pickle) — do solvera tylko liczby i ID; profilowanie dopiero na sygnał
(py-spy na żywym serwerze), nie prewencyjnie; koszt spawn procesu na Windows ukryty przez trzymanie puli żywej.

| Narzędzie | Rola w projekcie | Licencja |
| :--- | :--- | :--- |
| stdlib `asyncio`, `concurrent.futures` | Pętla UI; pula procesów/wątków pod `run.cpu_bound`/`io_bound` | PSF |
| py-spy | Profilowanie działającego serwera bez restartu | MIT |
| stdlib `cProfile` + snakeviz | Profilowanie offline przygotowania danych solvera | PSF / BSD-3 |

### Obszar 8: Bezpieczeństwo

**Rekomendacja:**
- Sekrety w `.env` (poza repo, w repo tylko `.env.example`) przez pydantic-settings.
- Własne proste logowanie: hasła argon2-cffi, sesje `app.storage.user` (podpisane ciasteczko,
  `storage_secret` z `secrets`).
- **Role w modelu danych od startu** (admin/dyspozytor/odczyt), na razie wszyscy z pełnymi uprawnieniami (decyzja).
- pydantic na każdej granicy (Excel = wejście niezaufane: limit rozmiaru, raport odrzuconych wierszy);
  SQL injection zamyka ORM (zakaz ręcznego sklejania SQL).
- Transport: HTTP w zaufanym LAN świadomie zaakceptowany — przy dostępie zdalnym w przyszłości: VPN,
  nie wystawianie aplikacji na świat.

**Sprawa krytyczna (procesowa):** jawne hasło do portalu e2open w `karta_projektu_i_wdrozenia.md` —
**zmienić hasło po stronie portalu i usunąć z dokumentu**; danych dostępowych nigdy nie wersjonować.

**Ryzyka:** Własna autentykacja = własna odpowiedzialność (minimum: argon2, wylogowanie po bezczynności);
`.env` czytelny lokalnie — ograniczyć dostęp do katalogu; baza nieszyfrowana (SQLCipher tylko na żądanie klienta).

| Biblioteka | Rola w projekcie | Licencja |
| :--- | :--- | :--- |
| pydantic-settings | Typowana konfiguracja z `.env`: klucze e2open, storage_secret, ścieżki | MIT |
| argon2-cffi | Hashowanie haseł kont użytkowników | MIT |
| stdlib `secrets` | Generowanie sekretów sesji | PSF |

### Obszar 9: Testy i jakość kodu

**Rekomendacja — trzy poziomy testów:**
1. **pytest** — reguły domenowe: FR-019 (nierozdzielność), FR-021 (warunki edycji palet), FR-022 (reguła kosztowa),
   FR-024 (termin +7 dni), import Excela.
2. **hypothesis** — testy własnościowe solvera: losowe instancje → niezmienniki każdego wyniku
   (pojemności nieprzekroczone, shipmenty nierozdzielone, ≤3 dropy, każde zlecenie w planie albo kolejce).
3. **Testy golden** na zamrożonych danych testowych (Excel → znany koszt/liczba pojazdów); scenariusze symulacyjne
   jako przypadki testowe. **Budżety wydajności z Obszaru 7 jako testy regresyjne.**

**Jakość kodu:** ruff (lint+format, zastępuje black/flake8/isort), mypy tylko na `domain/optimization/services`,
import-linter (reguły architektury z Obszaru 2), pre-commit spinający całość.

**Ryzyka:** Testy własnościowe wolne → limit solvera 2–5 s w testach + nocny profil dokładny;
hypothesis MPL-2.0 — wyłącznie dev, bez wpływu na dystrybucję; dyscyplina: niezmienniki solvera mają testy
zawsze, UI tylko tam, gdzie boli.

| Biblioteka (dev) | Rola w projekcie | Licencja |
| :--- | :--- | :--- |
| pytest + pytest-cov | Testy jednostkowe i golden; pokrycie | MIT |
| hypothesis | Testy własnościowe niezmienników solvera | MPL-2.0 (dev-only) |
| ruff | Lint + formatowanie jedną binarką | MIT |
| mypy | Statyczne typy w warstwach domenowych | MIT |
| import-linter | Egzekwowanie reguł zależności między modułami | BSD-2 |
| pre-commit | Automatyczne kontrole przy commicie | MIT |

### Obszar 10: Środowisko deweloperskie i zależności

**Rekomendacja:** uv (środowiska, lockfile `uv.lock`, zarządzanie wersją CPythona) + pyproject.toml;
CPython 3.12/3.13 przypięty; **git lokalny** (bez GitHuba — decyzja z Obszaru 13), kontrole jakości przez
pre-commit na maszynie dewelopera; opcjonalnie self-hosted Gitea (MIT), jeśli zespół zechce wspólne repo
z przeglądarką. Conda niepotrzebna — wszystkie zależności mają wheels na Windows.

**Wpływ na płynność:** Identyczne wersje na dev/serwerze (lockfile) — brak cichych regresji wydajności;
nowy CPython = darmowe kilkanaście+ % na czystym Pythonie.

**Ryzyka:** uv młode (wyjście awaryjne: pyproject.toml jest standardem → powrót do pip+venv w godzinę);
bez zdalnego repo kopie kodu = odpowiedzialność zespołu (git jest rozproszony — klon u każdego członka + na serwerze).

### Obszar 11: Pakowanie i dystrybucja

**Rekomendacja:** Bez PyInstallera i bez .exe. Wdrożenie: kopia kodu na PC-serwer + `uv sync` + autostart przez
Harmonogram zadań Windows (restart po awarii); aktualizacja skryptem: stop → pull/kopiuj + `uv sync` + migracje
Alembica (z backupem bazy przed) → start; instrukcja w `DEPLOY.md`. Klient końcowy = przeglądarka,
zero instalacji u dyspozytorów.

**Wpływ na płynność:** Koszt startu (import pandas itd.) ponoszony raz po restarcie PC, nie przy wejściu
użytkownika; aktualizacje poza oknami importu i godzinami pracy (~1–2 min przerwy).

**Ryzyka:** PC może zostać wyłączony / zrestartowany przez Windows Update — ustawić politykę restartów poza
oknami 5:30/11:30; eskalacja w razie potrzeby: usługa Windows przez WinSW (MIT);
w Fazie 2, gdy OSRM wymusi Dockera, rozważyć Docker Compose dla całości.

### Obszar 12: Logowanie, monitoring, obsługa błędów

**Rekomendacja — dwa osobne strumienie:**
1. **Logi techniczne (loguru):** `enqueue=True` (asynchronicznie, bezpieczne scalanie logów z procesu solvera),
   rotacja + retencja plików. Tryb `diagnose` dla tracebacków ze zmiennymi z procesów potomnych.
2. **Audyt biznesowy (tabela SQLite):** zatwierdzenia planów, zmiany palet (FR-021), rotacje kolejki (FR-020),
   wyniki importów — przeglądalny w UI, przechowywany bezterminowo.

**Obsługa błędów:** globalny handler wyjątków (ludzki komunikat + pełny kontekst do loga, nigdy stack trace na
ekran); błędy danych = raport walidacyjny, nie wyjątek; **baner statusu ostatniego importu** przy wejściu do
aplikacji (decyzja: bez e-maili na razie).

**Monitoring:** strona "Stan systemu" w aplikacji (importy, czasy solvera, rozmiar bazy, dysk, ogon błędów).
Prometheus/Grafana — świadomie pominięte.

**Backup:** nocne zadanie APScheduler przez sqlite3 backup API (spójna kopia bez zatrzymywania aplikacji)
na drugi dysk/udział sieciowy, retencja ~14 dni.

**Ryzyka:** loguru = de facto jeden maintainer (migracja na stdlib w godziny) [aktywność do weryfikacji];
logi i baza na tym samym dysku → backup na inny nośnik obowiązkowo.

| Biblioteka | Rola w projekcie | Licencja |
| :--- | :--- | :--- |
| loguru | Logi techniczne z rotacją i retencją | MIT |
| stdlib `sqlite3` (backup API) | Nocna spójna kopia bazy na drugi nośnik | PSF |
| APScheduler (już w stacku) | Harmonogram backupu i zadań porządkowych | MIT |

### Obszar 13: Komponenty chmurowe

**Decyzja: brak jakichkolwiek komponentów chmurowych.** System w 100% lokalny. Zastępstwa:

| Odrzucona usługa chmurowa | Lokalne zastępstwo |
| :--- | :--- |
| GitHub + Actions | git lokalny (klon u każdego członka + na serwerze) lub self-hosted Gitea; kontrole przez pre-commit |
| Publiczny Nominatim (geokodowanie) | Słownik współrzędnych w aplikacji (MVP) → self-hosted Photon (docelowo) |
| Publiczne kafelki OSM | Lokalny podkład Protomaps/PMTiles serwowany z własnego serwera [do weryfikacji technicznej] |
| Publiczne API routingu (openrouteservice) | Wyłącznie self-hosted OSRM, bez etapu pomostowego |
| Sentry / GlitchTip | loguru + baner statusu + strona "Stan systemu" |
| Backup do chmury | Udział sieciowy / NAS w firmie |

---

## 3. Pełna lista zależności (pod `pyproject.toml`)

```toml
[project]
name = "crossdock"
requires-python = ">=3.12"
dependencies = [
    "nicegui",            # UI: panel dyspozytora, mapa, tabele, wykresy
    "pydantic",           # modele domenowe + walidacja granic
    "pydantic-settings",  # konfiguracja i sekrety z .env
    "sqlalchemy",         # dostęp do SQLite, transakcje
    "alembic",            # migracje schematu
    "ortools",            # CP-SAT + Routing Solver
    "numpy",              # macierz odległości, wskaźniki
    "pandas",             # import Excela, agregacje raportów, eksport .xlsx
    "openpyxl",           # silnik .xlsx + formatowanie raportów
    "httpx",              # async HTTP: e2open (Faza 2), OSRM, Photon
    "geopy",              # adapter geokodera (Photon self-hosted)
    "apscheduler",        # okna importu 5:30/11:30, backup nocny
    "loguru",             # logi techniczne z rotacją
    "argon2-cffi",        # hashowanie haseł użytkowników
]

[dependency-groups]
dev = [
    "pytest",
    "pytest-cov",
    "hypothesis",       # testy własnościowe solvera (MPL-2.0, tylko dev)
    "ruff",
    "mypy",
    "import-linter",
    "pre-commit",
    "py-spy",
    "snakeviz",
]
```

Wersje celowo nieprzypięte w tym dokumencie — przypina je `uv.lock` przy inicjalizacji projektu (`uv add …`),
co gwarantuje aktualne i spójne wydania zamiast zgadywanych numerów.

Usługi poza pip: OSRM (Docker, Faza 2), Photon (JAR/Docker, gdy potrzebny),
plik PMTiles z ekstraktem Belgii + krajów ościennych.

---

## 4. Decyzje wymagające potwierdzenia

1. **Podkład mapy w wariancie 100% lokalnym (Protomaps/PMTiles)** — przyjęty jako konsekwencja odrzucenia chmury;
   wymaga weryfikacji technicznej (jakość podkładu, integracja protomaps-leaflet z NiceGUI).
   Alternatywa do rozważenia: mapa tras na pustym tle (sama geometria + punkty) w MVP.
2. **Geokodowanie w MVP przez ręczny słownik współrzędnych** — założenie: liczba unikalnych lokalizacji
   odbioru/dostawy jest mała (dziesiątki). Jeśli będzie ich setki, Photon trzeba postawić wcześniej.
3. **Budżety wydajności** (UI < 100 ms, import < 5 s, solver 30–60 s) — przyjęte przez architekta,
   zaakceptowane milcząco.
4. **Progi biznesowe z notatki SRS** (zapełnienie ≥ 90%, maks. 3 dropy, próg 15% dla buforowania,
   12 h na zmianę palet) — pochodzą z *propozycji* w sekcji 9.2 notatki, nie z potwierdzeń klienta;
   muszą trafić do konfiguracji, nie do kodu.
5. **Format pliku Excel z e2open oraz kształt API i danych GPS** — niewiadome blokujące szczegóły
   implementacji `ingest/`; architektura (porty) na to gotowa.
6. **Reakcja na wzrost liczby palet po akceptacji, gdy ładunek przestaje się mieścić** (luka 9.3 SRS) —
   wymaga decyzji klienta; proponowany kierunek: plan oznaczany jako "wymaga przeplanowania" + powiadomienie w UI.
7. **OSRM vs Valhalla** — jeśli trasy muszą respektować ograniczenia ciężarówkowe (tonaż, wysokość),
   wybór przechyli się na Valhallę; decyzja przy starcie Fazy 2.
8. **Zmiana hasła do portalu e2open** i usunięcie go z dokumentacji — poza stackiem,
   ale wymaga działania natychmiast.

---

## 5. Odrzucone opcje i dlaczego

| Opcja | Obszar | Powód odrzucenia |
| :--- | :--- | :--- |
| Aplikacja desktopowa | 1 | Kilku użytkowników wymusiłoby i tak architekturę klient–serwer + dystrybucję na stanowiska |
| Streamlit | 1 | Model "przerysuj wszystko" psuje responsywność interaktywnego panelu przy wielu sesjach |
| SPA React/Vue + FastAPI | 1 | Drugi stack (JS) przy jednym programiście; pozostaje ścieżką migracji (NiceGUI stoi na FastAPI) |
| Mikrousługi, event bus, framework DI | 2 | Przerost dla zespołu z jednym programistą i dziesiątek zleceń dziennie |
| Własne heurystyki zamiast solvera | 3 | Odtwarzanie koła; gorsze wyniki przy większym koszcie |
| VROOM | 3 | Sztywny model problemu — trudno wcisnąć FR-019 i regułę buforowania; ewentualnie w Fazie 2 |
| polars | 4 | Przewagi dopiero przy milionach wierszy — nieosiągalnych w tym projekcie |
| PDF w raportach (reportlab/weasyprint) | 4 | Decyzja: Excel/CSV wystarczy |
| PostgreSQL | 5 | Usługa do administrowania na biurowym PC bez zysku przy jednym procesie piszącym; otwarta ścieżka migracji przez SQLAlchemy |
| async-SQLAlchemy / aiosqlite | 5 | Złożoność bez mierzalnego zysku przy zapytaniach sub-milisekundowych |
| Celery + Redis | 7 | Dwa serwisy do utrzymania zamiast `ProcessPoolExecutor` dla jednego równoczesnego zadania |
| Własne rozszerzenia C/Cython/numba | 7 | Ciężka praca już w natywnych bibliotekach; Python jest tylko klejem |
| fastapi-users, OAuth/LDAP | 8 | Własne logowanie ~100 linii vs naginanie cudzych konwencji przy kilku kontach |
| Vault / keyring | 8 | Teatr bezpieczeństwa na pojedynczym PC; `.env` + uprawnienia katalogu wystarczą |
| unittest (stdlib) | 9 | Rozwlekła składnia; przewaga pytest powszechnie uznana |
| conda | 10 | Wszystkie zależności mają wheels na Windows; ciężki ekosystem bez potrzeby |
| Poetry / pip+venv | 10 | Brak przewag nad uv (wolniejsze, nie zarządzają wersją Pythona); pip+venv zostaje wyjściem awaryjnym |
| PyInstaller / .exe | 11 | Rozwiązuje nieistniejący problem; kruche przy ortools/nicegui, utrudnia aktualizacje i migracje |
| NSSM | 11 | Nieaktywne od lat — łamie zasadę doboru; w razie potrzeby WinSW |
| Prometheus + Grafana | 12 | Monitoring jednego procesu na jednym PC załatwia strona statusu w aplikacji |
| structlog | 12 | Logi JSON bez maszynowego konsumenta to koszt bez zysku |
| GitHub/Actions, publiczny Nominatim, publiczne kafelki OSM, openrouteservice API, Sentry, backup w chmurze | 13 | **Decyzja projektowa: zero chmury**; wszystkie mają lokalne zastępstwa (git lokalny/Gitea + pre-commit, słownik współrzędnych/Photon, PMTiles, OSRM, loguru+baner, NAS) |
