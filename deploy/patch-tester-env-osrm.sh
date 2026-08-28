#!/usr/bin/env bash
# Force CROSSDOCK_USE_OSRM=true in deploy/.env.t1 … t4 (idempotent).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

for i in 1 2 3 4; do
  dest="deploy/.env.t${i}"
  if [[ ! -f "$dest" ]]; then
    echo "Brak $dest — najpierw: bash deploy/gen-tester-envs.sh"
    exit 1
  fi
  if grep -q '^CROSSDOCK_USE_OSRM=' "$dest"; then
    sed -i 's/^CROSSDOCK_USE_OSRM=.*/CROSSDOCK_USE_OSRM=true/' "$dest"
  else
    echo 'CROSSDOCK_USE_OSRM=true' >>"$dest"
  fi
  if grep -q '^CROSSDOCK_OSRM_URL=' "$dest"; then
    sed -i 's|^CROSSDOCK_OSRM_URL=.*|CROSSDOCK_OSRM_URL=http://osrm:5000|' "$dest"
  else
    echo 'CROSSDOCK_OSRM_URL=http://osrm:5000' >>"$dest"
  fi
  echo "OK $dest → USE_OSRM=true, OSRM_URL=http://osrm:5000"
done
