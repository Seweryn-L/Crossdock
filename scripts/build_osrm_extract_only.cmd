@echo off
REM Resume OSRM build from extract (skip merge). Use after merge succeeded but extract OOM'd.
REM Run: scripts\build_osrm_extract_only.cmd [threads]
REM Default threads=4 (less RAM than OSRM default 16).

setlocal
cd /d "%~dp0.."
set OSRM=%CD%\data\osrm
set GRAPH=be-nl-de-fr.osrm
set THREADS=%1
if "%THREADS%"=="" set THREADS=4

if not exist "%OSRM%\be-nl-de-fr.osm.pbf" (
  echo Missing %OSRM%\be-nl-de-fr.osm.pbf — run build_osrm_be_nl_de_fr.cmd first.
  exit /b 1
)

echo Using %THREADS% threads. Docker Desktop needs ~16 GB+ RAM for this dataset.
echo If it dies again: increase Docker memory, or run with fewer threads, e.g.:
echo   scripts\build_osrm_extract_only.cmd 2
echo.

echo ==^> 2/4 osrm-extract (long — 30-120 min)
docker run --rm -t -v "%OSRM%:/data" ghcr.io/project-osrm/osrm-backend:v5.27.1 osrm-extract -p /opt/car.lua -t %THREADS% /data/be-nl-de-fr.osm.pbf
if errorlevel 1 (
  echo.
  echo Extract failed — usually out of memory. Docker Desktop -^> Settings -^> Resources -^> Memory: set 16-24 GB.
  exit /b 1
)

echo ==^> 3/4 osrm-partition
docker run --rm -t -v "%OSRM%:/data" ghcr.io/project-osrm/osrm-backend:v5.27.1 osrm-partition /data/%GRAPH%
if errorlevel 1 exit /b 1

echo ==^> 4/4 osrm-customize
docker run --rm -t -v "%OSRM%:/data" ghcr.io/project-osrm/osrm-backend:v5.27.1 osrm-customize /data/%GRAPH%
if errorlevel 1 exit /b 1

echo Done. Start: docker compose -f docker-compose.osrm.yml --profile osrm up -d
exit /b 0
