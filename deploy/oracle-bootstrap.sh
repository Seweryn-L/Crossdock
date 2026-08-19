#!/usr/bin/env bash
# Bootstrap Crossdock demo on Ubuntu (Oracle Cloud VM).
set -euo pipefail

if [[ ! -f .env ]]; then
  echo "Brak .env — skopiuj deploy/.env.demo.example i uzupełnij sekrety."
  exit 1
fi

mkdir -p data
docker compose up -d --build
docker compose ps
echo
echo "Demo powinno być dostępne na porcie 8080."
echo "Sprawdź logi: docker compose logs -f crossdock"
