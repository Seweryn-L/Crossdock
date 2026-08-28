#!/usr/bin/env bash
# Start 4 isolated Crossdock tester instances + shared OSRM on Oracle VM / Docker.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck source=common-testers.sh
source deploy/common-testers.sh

missing=0
for i in 1 2 3 4; do
  if [[ ! -f "deploy/.env.t${i}" ]]; then
    echo "Brak deploy/.env.t${i}"
    missing=1
  fi
done
if [[ "$missing" -eq 1 ]]; then
  echo "Wygeneruj env: bash deploy/gen-tester-envs.sh"
  exit 1
fi

if ! osrm_graph_ready; then
  echo "Brak grafu OSRM: data/osrm/be-nl-de-fr.osrm"
  echo
  echo "Opcje:"
  echo "  1) Skopiuj gotowy katalog data/osrm/ z maszyny dev (gdzie budowałeś mapę)"
  echo "  2) Zbuduj na VM — patrz docs/osrm_local.md (wymaga ~16 GB RAM i PBF-y w data/)"
  echo
  echo "Szybki test czy katalog istnieje:"
  echo "  ls -la data/osrm/"
  exit 1
fi

bash deploy/patch-tester-env-osrm.sh

mkdir -p data/t1 data/t2 data/t3 data/t4

testers_compose up -d --build
testers_compose ps

wait_for_osrm

echo
echo "Instancje testerów (OSRM włączony — trasy po drogach po ponownym Generuj):"
echo "  http://PUBLIC_IP:8081  (t1, admin / hasło z deploy/.env.t1)"
echo "  http://PUBLIC_IP:8082  (t2)"
echo "  http://PUBLIC_IP:8083  (t3)"
echo "  http://PUBLIC_IP:8084  (t4)"
echo
echo "OSRM (wspólny dla wszystkich): http://PUBLIC_IP:5000"
echo "Logi: testers_compose logs -f"
echo "     docker compose -f docker-compose.testers.yml -f docker-compose.osrm.yml --profile osrm logs -f"
echo
echo "Otwórz porty 8081–8084 (i opcjonalnie 5000) w Oracle Security List."
