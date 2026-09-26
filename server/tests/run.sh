#!/bin/bash
# Applies the Supabase migrations to a throwaway local PostgreSQL and runs the market
# checks. Needs the PostgreSQL server binaries (e.g. apt install postgresql).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PGBIN="${PGBIN:-$(ls -d /usr/lib/postgresql/*/bin | tail -1)}"
DIR="$(mktemp -d)"
trap '"$PGBIN/pg_ctl" -D "$DIR/data" stop -m immediate >/dev/null 2>&1 || true; rm -rf "$DIR"' EXIT
if [ "$(id -u)" = "0" ]; then RUN="runuser -u postgres --"; chown -R postgres "$DIR"; else RUN=""; fi
$RUN "$PGBIN/initdb" -D "$DIR/data" -U postgres >/dev/null
$RUN "$PGBIN/pg_ctl" -D "$DIR/data" -o "-k $DIR -c listen_addresses=''" -w start >/dev/null
PSQL=(psql -h "$DIR" -U postgres -d postgres -v ON_ERROR_STOP=1 -q)
"${PSQL[@]}" -f "$HERE/auth_stub.sql"
for f in "$HERE"/../supabase/migrations/*.sql; do "${PSQL[@]}" -f "$f"; done
"${PSQL[@]}" -f "$HERE/market_test.sql"
