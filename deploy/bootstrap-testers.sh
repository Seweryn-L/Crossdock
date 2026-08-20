#!/usr/bin/env bash
# Start 4 isolated Crossdock tester instances on Oracle VM / Docker.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

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

mkdir -p data/t1 data/t2 data/t3 data/t4

docker compose -f docker-compose.testers.yml up -d --build
docker compose -f docker-compose.testers.yml ps

echo
echo "Instancje testerów:"
echo "  http://PUBLIC_IP:8081  (t1)"
echo "  http://PUBLIC_IP:8082  (t2)"
echo "  http://PUBLIC_IP:8083  (t3)"
echo "  http://PUBLIC_IP:8084  (t4)"
echo "Login: admin + hasło z deploy/.env.tN (domyślnie tester1…tester4 po gen-tester-envs.sh)"
echo "Logi: docker compose -f docker-compose.testers.yml logs -f"
echo
echo "Otwórz porty 8081–8084 w Oracle Security List / iptables."
