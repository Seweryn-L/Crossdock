#!/usr/bin/env bash
# Smoke test: OSRM + tester containers can reach osrm:5000.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck source=common-testers.sh
source deploy/common-testers.sh

echo "=== Graf OSRM na dysku ==="
if osrm_graph_ready; then
  echo "OK data/osrm/be-nl-de-fr.osrm"
else
  echo "BRAK data/osrm/be-nl-de-fr.osrm"
  exit 1
fi

echo
echo "=== OSRM na hoście (port 5000) ==="
wait_for_osrm

echo
echo "=== USE_OSRM w env testerów ==="
for i in 1 2 3 4; do
  f="deploy/.env.t${i}"
  use="$(grep '^CROSSDOCK_USE_OSRM=' "$f" | cut -d= -f2)"
  url="$(grep '^CROSSDOCK_OSRM_URL=' "$f" | cut -d= -f2)"
  echo "t${i}: USE_OSRM=${use} URL=${url}"
  if [[ "$use" != "true" ]]; then
    echo "  → uruchom: bash deploy/patch-tester-env-osrm.sh && bash deploy/bootstrap-testers.sh"
    exit 1
  fi
done

echo
echo "=== OSRM z kontenera crossdock-t1 ==="
testers_compose exec -T crossdock-t1 python -c "
import httpx
r = httpx.get('http://osrm:5000/route/v1/driving/4.35,50.85;2.35,48.85', timeout=10)
r.raise_for_status()
assert r.json().get('code') == 'Ok', r.text
print('OK crossdock-t1 widzi osrm:5000')
"

echo
echo "=== HTTP testerów ==="
for port in 8081 8082 8083 8084; do
  code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${port}/login" || true)"
  echo "localhost:${port}/login → ${code}"
done

echo
echo "Wszystko OK. W UI: zaimportuj Excel → Generuj → mapa powinna mieć trasy po drogach."
echo "(Stare generacje sprzed włączenia OSRM wymagają ponownego Generuj.)"
