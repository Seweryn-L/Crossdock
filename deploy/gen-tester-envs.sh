#!/usr/bin/env bash
# Create deploy/.env.t1 … t4 from the tester template (unique secrets + passwords).
# Existing files are NOT overwritten.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

TEMPLATE="deploy/.env.tester.example"
if [[ ! -f "$TEMPLATE" ]]; then
  echo "Brak $TEMPLATE"
  exit 1
fi

gen_secret() {
  python3 -c "import secrets; print(secrets.token_hex(32))"
}

for i in 1 2 3 4; do
  dest="deploy/.env.t${i}"
  if [[ -f "$dest" ]]; then
    echo "Pomijam $dest (już istnieje)."
    continue
  fi
  secret="$(gen_secret)"
  # Default passwords are for lab testing only — change before sharing the VM widely.
  password="tester${i}"
  sed \
    -e "s/^CROSSDOCK_STORAGE_SECRET=.*/CROSSDOCK_STORAGE_SECRET=${secret}/" \
    -e "s/^CROSSDOCK_ADMIN_PASSWORD=.*/CROSSDOCK_ADMIN_PASSWORD=${password}/" \
    "$TEMPLATE" >"$dest"
  echo "Utworzono $dest (admin / ${password})"
done

echo
echo "Gotowe. Możesz zmienić hasła w deploy/.env.tN (nano)."
echo "Start: bash deploy/bootstrap-testers.sh"
