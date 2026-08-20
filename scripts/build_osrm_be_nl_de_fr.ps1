# Build one OSRM graph from local PBF files (BE + NL + DE + FR).
# Run from repo root:  .\scripts\build_osrm_be_nl_de_fr.ps1
#
# Requires: Docker Desktop, ~25 GB free disk, 16 GB+ RAM recommended for extract.
# Input files (already in data/):
#   belgium-260819.osm.pbf
#   netherlands-260819.osm.pbf
#   germany-latest.osm.pbf
#   france-260819.osm.pbf
# Output: data/osrm/be-nl-de-fr.osrm*

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$DATA = Join-Path $PWD "data"
$OSRM = Join-Path $DATA "osrm"
$MERGED = Join-Path $OSRM "be-nl-de-fr.osm.pbf"
$GRAPH = "be-nl-de-fr.osrm"

$pbf = @(
    (Join-Path $DATA "belgium-260819.osm.pbf"),
    (Join-Path $DATA "netherlands-260819.osm.pbf"),
    (Join-Path $DATA "germany-latest.osm.pbf"),
    (Join-Path $DATA "france-260819.osm.pbf")
)
foreach ($f in $pbf) {
    if (-not (Test-Path $f)) {
        throw "Missing PBF: $f"
    }
}
New-Item -ItemType Directory -Force -Path $OSRM | Out-Null

Write-Host "==> 1/4 osmium merge -> $MERGED"
docker run --rm `
    -v "${DATA}:/data" `
    stefda/osmium-tool `
    osmium merge `
    /data/belgium-260819.osm.pbf `
    /data/netherlands-260819.osm.pbf `
    /data/germany-latest.osm.pbf `
    /data/france-260819.osm.pbf `
    -o /data/osrm/be-nl-de-fr.osm.pbf

Write-Host "==> 2/4 osrm-extract (long — 30-120 min, needs ~16 GB Docker RAM)"
Write-Host "    Using 4 threads. If OOM: Docker Desktop -> Settings -> Resources -> Memory 16-24 GB"
docker run --rm -t `
    -v "${OSRM}:/data" `
    ghcr.io/project-osrm/osrm-backend:v5.27.1 `
    osrm-extract -p /opt/car.lua -t 4 /data/be-nl-de-fr.osm.pbf
if ($LASTEXITCODE -ne 0) {
    Write-Host "Extract failed — often out of memory. Re-run: scripts\build_osrm_extract_only.cmd 4"
    exit 1
}

Write-Host "==> 3/4 osrm-partition"
docker run --rm -t `
    -v "${OSRM}:/data" `
    ghcr.io/project-osrm/osrm-backend:v5.27.1 `
    osrm-partition /data/$GRAPH

Write-Host "==> 4/4 osrm-customize"
docker run --rm -t `
    -v "${OSRM}:/data" `
    ghcr.io/project-osrm/osrm-backend:v5.27.1 `
    osrm-customize /data/$GRAPH

Write-Host ""
Write-Host "Done. Start routing:"
Write-Host "  docker compose -f docker-compose.osrm.yml --profile osrm up -d"
Write-Host ""
Write-Host "Smoke test:"
Write-Host '  curl "http://127.0.0.1:5000/route/v1/driving/4.35,50.85;2.35,48.85?overview=false"'
