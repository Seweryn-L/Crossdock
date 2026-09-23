#!/usr/bin/env bash
set -euo pipefail
cd ~/Crossdock
COMPOSE="docker compose -f docker-compose.testers.yml -f docker-compose.osrm.yml --profile osrm"
$COMPOSE stop crossdock-t1 crossdock-t2 crossdock-t3 crossdock-t4
for d in data/t1 data/t2 data/t3 data/t4; do
  echo "czyszcze $d"
  sudo rm -f "$d/crossdock.db" "$d/crossdock.db-wal" "$d/crossdock.db-shm"
  sudo rm -f "$d"/backups/crossdock_*.db || true
done
$COMPOSE up -d crossdock-t1 crossdock-t2 crossdock-t3 crossdock-t4
sleep 6
for p in 8081 8082 8083 8084; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$p/login")
  echo "$p -> $code"
done
for n in 1 2 3 4; do
  out=$(docker exec "crossdock-t$n" uv run python -c "from sqlalchemy import text; from crossdock.storage.database import session_scope
with session_scope() as s:
 print(s.execute(text('select count(*) from orders')).scalar(), s.execute(text('select count(*) from assignment_runs')).scalar())")
  echo "t$n: orders/runs = $out"
done
echo "done"
