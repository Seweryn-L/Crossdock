#!/bin/sh
set -eu

mkdir -p data data/logs data/backups

# Honour custom DB / backup paths (e.g. data/t1 when bind-mounted).
if [ -n "${CROSSDOCK_DB_PATH:-}" ]; then
  mkdir -p "$(dirname "$CROSSDOCK_DB_PATH")"
fi
if [ -n "${CROSSDOCK_BACKUP_DIR:-}" ]; then
  mkdir -p "$CROSSDOCK_BACKUP_DIR"
fi

uv run alembic upgrade head

exec uv run crossdock
