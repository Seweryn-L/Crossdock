# OSRM lokalnie — BE + NL + DE + FR

## Twoje pliki wejściowe (już w `data/`)

| Plik | ~rozmiar |
|------|----------|
| `belgium-260819.osm.pbf` | 0,7 GB |
| `netherlands-260819.osm.pbf` | 1,4 GB |
| `germany-latest.osm.pbf` | 4,8 GB |
| `france-260819.osm.pbf` | 5,1 GB |

OSRM potrzebuje **jednego** grafu — najpierw scalamy 4 pliki, potem preprocessing.

## Szybka ścieżka

Z katalogu projektu (bez zmiany Execution Policy — użyj `.cmd`):

```cmd
cd /d D:\ja\TY100\Zadanie1\crossdock
scripts\build_osrm_be_nl_de_fr.cmd
```

Alternatywa PowerShell (jednorazowo, bez zmiany polityki systemowej):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_osrm_be_nl_de_fr.ps1
```

Extract może trwać **30–120 min** i wymaga **16 GB+ RAM przydzielonego Docker Desktop** (DE+FR to duże mapy).

### Docker Desktop — pamięć (ważne)

Settings → Resources → **Memory: 16–24 GB** (domyślnie często 8 GB → extract się wywala bez czytelnego błędu).

### Extract padł po „Parse ways and nodes”?

Merge już masz (`data/osrm/be-nl-de-fr.osm.pbf` ~12 GB). **Nie rób merge od nowa** — wznów extract:

```cmd
scripts\build_osrm_extract_only.cmd 4
```

Przy dalszych OOM spróbuj `2` wątków:

```cmd
scripts\build_osrm_extract_only.cmd 2
```

## Ręcznie — te same kroki

```powershell
cd D:\ja\TY100\Zadanie1\crossdock
mkdir data\osrm -Force

# 1) Scal 4 mapy (obraz z Docker Hub — ghcr.io/osmcode często blokuje „denied”)
docker run --rm `
  -v "${PWD}/data:/data" `
  stefda/osmium-tool `
  osmium merge `
  /data/belgium-260819.osm.pbf `
  /data/netherlands-260819.osm.pbf `
  /data/germany-latest.osm.pbf `
  /data/france-260819.osm.pbf `
  -o /data/osrm/be-nl-de-fr.osm.pbf

# 2) extract
docker run --rm -t `
  -v "${PWD}/data/osrm:/data" `
  ghcr.io/project-osrm/osrm-backend:v5.27.1 `
  osrm-extract -p /opt/car.lua /data/be-nl-de-fr.osm.pbf

# 3) partition + customize (MLD)
docker run --rm -t `
  -v "${PWD}/data/osrm:/data" `
  ghcr.io/project-osrm/osrm-backend:v5.27.1 `
  osrm-partition /data/be-nl-de-fr.osrm

docker run --rm -t `
  -v "${PWD}/data/osrm:/data" `
  ghcr.io/project-osrm/osrm-backend:v5.27.1 `
  osrm-customize /data/be-nl-de-fr.osrm
```

W `data/osrm/` powstanie m.in. `be-nl-de-fr.osrm` + pliki towarzyszące.

## Start OSRM

```powershell
docker compose -f docker-compose.osrm.yml --profile osrm up -d
```

Test (Bruksela → Paryż):

```powershell
curl "http://127.0.0.1:5000/route/v1/driving/4.35,50.85;2.35,48.85?overview=false"
```

Oczekiwane: `"code":"Ok"`.

## Aplikacja crossdock

W `.env`:

```text
CROSSDOCK_USE_OSRM=true
CROSSDOCK_OSRM_URL=http://127.0.0.1:5000
CROSSDOCK_OSRM_PROFILE=driving
```

Aplikacja w Compose (ta sama sieć): `CROSSDOCK_OSRM_URL=http://osrm:5000`.

## Uwagi

- **Nie** uruchamiaj osobno 4 instancji OSRM per kraj — trasy przez granice wtedy nie zadziałają.
- Jeśli extract pada na brak pamięci, rozważ mniejsze wycinki Geofabrik (np. NRW zamiast całych Niemiec).
