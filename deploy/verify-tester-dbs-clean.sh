#!/usr/bin/env bash
set -euo pipefail
for p in 8081 8082 8083 8084; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$p/login")
  echo "$p -> $code"
done
for n in 1 2 3 4; do
  out=$(docker exec "crossdock-t$n" uv run python -c "from sqlalchemy import text; from crossdock.storage.database import session_scope
with session_scope() as s:
 print(s.execute(text('select count(*) from orders')).scalar(), s.execute(text('select count(*) from assignment_runs')).scalar())")
  echo "t$n: orders runs = $out"
done
ls -lah ~/Crossdock/data/t{1,2,3,4}/crossdock.db
