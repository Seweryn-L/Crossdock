# Crossdock

Aplikacja dla dyspozytora magazynu przeładunkowego. Wgrywa się zlecenia z Excela, program układa z nich trasy całopojazdowe, a wynik widać na liście planów, na mapie i w raportach.

Interfejs jest po polsku, w przeglądarce. Dane siedzą w lokalnej bazie SQLite, w katalogu `data/`.

## Wymagania

Python 3.12 i [uv](https://docs.astral.sh/uv/).

## Pierwsze uruchomienie

W katalogu projektu skopiuj wzorzec konfiguracji i uzupełnij dwie wartości:

```powershell
copy .env.example .env
```

- `CROSSDOCK_STORAGE_SECRET` — długi losowy ciąg, podpis sesji logowania
- `CROSSDOCK_ADMIN_PASSWORD` — hasło konta `admin`; używane tylko wtedy, gdy baza jest pusta

Sekret:

```powershell
uv run python -c "import secrets; print(secrets.token_hex(32))"
```

Start:

```powershell
uv sync
uv run alembic upgrade head
uv run crossdock
```

Potem w przeglądarce: `http://127.0.0.1:8080`, login `admin`. Z innej maszyny w tej samej sieci wchodzi się na adres tego komputera, port 8080.

Przy pierwszym starcie powstaje katalog `data/` (baza, logi, kopie). Kopia bazy robi się codziennie o 02:30, zostaje 14 ostatnich plików. Godzinę i liczbę kopii zmienia się w `.env`.

Reszta ustawień (stawka za kilometr, limit punktów na trasie, współrzędne magazynu, mapowanie kolumn Excela) też jest w `.env` i w `config/`. Opis przy każdej zmiennej jest w `.env.example`.

## Co robi program

- import zleceń z Excela w układzie raportu e2open (nagłówek w 3. wierszu; nazwy kolumn w `config/excel_column_mapping.json`)
- układanie tras: wypełnienie auta, limit rozładunków, koszt kilometra (OR-Tools)
- plany, mapa, raporty, kolejka magazynu, ustawienia
- konto `admin` przy pustej bazie

Bez dodatkowego serwera odległości liczone są w linii prostej. Kilometry po drogach i geometria trasy na mapie wymagają OSRM, opisanego niżej.

Startowa flota (bus, truck, firanka) wpisuje się sama, gdy tabela pojazdów jest pusta. Pojemności są orientacyjne i da się je zmienić w ustawieniach.

## Docker

Przy gotowym pliku `.env`:

```powershell
docker compose up -d --build
```

Kontener sam odpala migracje i serwer. Baza zostaje w `./data` na hoście, port 8080.

## Odległości drogowe (OSRM)

Graf dla Belgii, Holandii, Niemiec i Francji buduje skrypt `scripts/build_osrm_be_nl_de_fr.ps1`. Wynik ma trafić do `data/osrm/`. W `.env`:

```
CROSSDOCK_USE_OSRM=true
CROSSDOCK_OSRM_URL=http://127.0.0.1:5000
```

Serwer tras:

```powershell
docker compose -f docker-compose.osrm.yml --profile osrm up -d
```

## Testy

```powershell
uv sync --group dev
uv run pytest
```

W `tests/fixtures/` są przykładowe pliki Excel.

## Układ katalogów

```
crossdock/    aplikacja
tests/        testy
alembic/      migracje bazy
config/       mapowanie Excela i współrzędne lokalizacji
deploy/       przykład kilku instancji na jednej maszynie
scripts/      budowa grafu OSRM
docker/       skrypt startu kontenera
```

Pliku `.env` w tej paczce nie ma. Hasła uzupełnia się lokalnie, ze wzorca `.env.example`.
