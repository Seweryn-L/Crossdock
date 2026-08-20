@echo off
REM Build OSRM graph BE+NL+DE+FR — no PowerShell execution policy needed.
REM Run from anywhere:  scripts\build_osrm_be_nl_de_fr.cmd

setlocal
cd /d "%~dp0.."
if errorlevel 1 exit /b 1

set DATA=%CD%\data
set OSRM=%DATA%\osrm
if not exist "%OSRM%" mkdir "%OSRM%"

if not exist "%DATA%\belgium-260819.osm.pbf" (
  echo Missing: %DATA%\belgium-260819.osm.pbf
  exit /b 1
)
if not exist "%DATA%\netherlands-260819.osm.pbf" (
  echo Missing: %DATA%\netherlands-260819.osm.pbf
  exit /b 1
)
if not exist "%DATA%\germany-latest.osm.pbf" (
  echo Missing: %DATA%\germany-latest.osm.pbf
  exit /b 1
)
if not exist "%DATA%\france-260819.osm.pbf" (
  echo Missing: %DATA%\france-260819.osm.pbf
  exit /b 1
)

echo ==^> 1/4 osmium merge
docker run --rm -v "%DATA%:/data" stefda/osmium-tool osmium merge /data/belgium-260819.osm.pbf /data/netherlands-260819.osm.pbf /data/germany-latest.osm.pbf /data/france-260819.osm.pbf -o /data/osrm/be-nl-de-fr.osm.pbf
if errorlevel 1 exit /b 1

echo ==^> 2/4 osrm-extract (long — 30-120 min, needs ~16 GB Docker RAM)
echo     Using 4 threads. If OOM: Docker Desktop -^> Settings -^> Resources -^> Memory 16-24 GB
docker run --rm -t -v "%OSRM%:/data" ghcr.io/project-osrm/osrm-backend:v5.27.1 osrm-extract -p /opt/car.lua -t 4 /data/be-nl-de-fr.osm.pbf
if errorlevel 1 (
  echo Extract failed — often out of memory. Re-run after raising Docker memory:
  echo   scripts\build_osrm_extract_only.cmd 4
  exit /b 1
)

echo ==^> 3/4 osrm-partition
docker run --rm -t -v "%OSRM%:/data" ghcr.io/project-osrm/osrm-backend:v5.27.1 osrm-partition /data/be-nl-de-fr.osrm
if errorlevel 1 exit /b 1

echo ==^> 4/4 osrm-customize
docker run --rm -t -v "%OSRM%:/data" ghcr.io/project-osrm/osrm-backend:v5.27.1 osrm-customize /data/be-nl-de-fr.osrm
if errorlevel 1 exit /b 1

echo.
echo Done. Start OSRM:
echo   docker compose -f docker-compose.osrm.yml --profile osrm up -d
exit /b 0
