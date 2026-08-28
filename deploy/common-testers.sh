#!/usr/bin/env bash
# Shared helpers for the 4-tester Docker stack (with OSRM).
set -euo pipefail

TESTERS_COMPOSE_FILES=(
  -f docker-compose.testers.yml
  -f docker-compose.osrm.yml
  --profile osrm
)

testers_compose() {
  docker compose "${TESTERS_COMPOSE_FILES[@]}" "$@"
}

osrm_graph_ready() {
  # MLD preprocessing often leaves only be-nl-de-fr.osrm.* shards (no bare .osrm file).
  local base="data/osrm/be-nl-de-fr.osrm"
  [[ -f "$base" ]] && return 0
  [[ -f "${base}.mldgr" || -f "${base}.fileIndex" || -f "${base}.geometry" ]]
}

wait_for_osrm() {
  local url="http://127.0.0.1:5000/route/v1/driving/4.35,50.85;2.35,48.85?overview=false"
  local i
  echo "Czekam na OSRM (port 5000)..."
  for i in $(seq 1 90); do
    if curl -sf "$url" 2>/dev/null | grep -q '"code":"Ok"'; then
      echo "OSRM odpowiada OK."
      return 0
    fi
    sleep 2
  done
  echo "OSRM nie odpowiedział w czasie — sprawdź: testers_compose logs osrm"
  return 1
}
