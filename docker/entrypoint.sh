#!/bin/sh
set -eu

mkdir -p data data/logs data/backups

uv run alembic upgrade head

exec uv run crossdock
